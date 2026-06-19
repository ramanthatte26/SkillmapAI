"""
SkillMap AI — AI Module Generation Service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Handles communication with OpenRouter API to organize videos into learning modules.
Includes robust fallback for when API configuration is missing or requests fail.
"""

import json
import logging
from pydantic import BaseModel, Field

import httpx

from app.config import Settings, get_settings
from app.utils.exceptions import BadRequestException

logger = logging.getLogger(__name__)


class AIModuleSchema(BaseModel):
    name: str = Field(..., description="Short name of the module")
    description: str = Field(..., description="Brief summary of what the module covers")
    video_positions: list[int] = Field(
        ...,
        description="0-indexed positions of the videos belonging to this module",
    )


class AIModulesOutput(BaseModel):
    modules: list[AIModuleSchema]


class AIService:
    """
    Connects to OpenRouter to group video titles into a structured set of modules.
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def generate_learning_modules(
        self,
        roadmap_title: str,
        video_titles: list[str],
    ) -> list[dict]:
        """
        Send roadmap title and video titles to OpenRouter Chat Completions endpoint,
        demanding a structured JSON response mapping videos to learning modules.

        If the service fails, fallback to local chunking.
        """
        if not self.settings.openrouter_api_key:
            logger.warning("OPENROUTER_API_KEY is empty. Real AI module generation cannot proceed.")
            raise BadRequestException(
                "OpenRouter API key is missing. Please set OPENROUTER_API_KEY in your backend .env file."
            )

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.frontend_url,
            "X-Title": "SkillMap AI",
        }

        # Clear, strict system prompt detailing the target schema.
        system_prompt = (
            "You are an expert curriculum designer and learning architect.\n"
            "Your task is to take the title of a learning roadmap and an ordered list of video titles, "
            "and group these videos into structured learning modules based on topic similarity and educational progression.\n"
            "Each video has an index (position) corresponding to its order in the list (starting from 0).\n\n"
            "You must return a JSON object that strictly conforms to the following schema:\n"
            "{\n"
            "  \"modules\": [\n"
            "    {\n"
            "      \"name\": \"Module Name\",\n"
            "      \"description\": \"Module Description\",\n"
            "      \"video_positions\": [0, 1, 2]\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "1. Group videos based on educational topic similarity and preserve learning progression (do not group unrelated topics together).\n"
            "2. Generate highly topic-specific module names that reflect the subject matter (e.g. 'Python Fundamentals', 'Control Flow & Functions', 'Object-Oriented Programming', 'File Handling', 'Data Structures').\n"
            "3. Strictly avoid generic, boilerplate module names such as 'Fundamentals & Core Principles', 'Core Concepts', 'Deep Dive', 'Practical Applications', 'Advanced Workflows', or 'Conclusion'.\n"
            "4. Every single video in the input list must belong to exactly one module. Do not skip or duplicate any video.\n"
            "5. The values in video_positions must correspond exactly to the 0-indexed positions of the videos in the input list.\n"
            "6. Preserve the chronological/logical video order. If video A comes before video B in the list, then the module containing A should either be the same as or come before the module containing B.\n"
            "7. Keep module names and descriptions concise, descriptive, and engaging.\n"
            "8. Output ONLY valid, raw JSON. Do not wrap it in markdown code blocks, do not write introductory/concluding text, and do not include explanations."
        )

        user_content = (
            f"Roadmap Title: {roadmap_title}\n"
            f"Videos:\n" + "\n".join(f"{idx}: {title}" for idx, title in enumerate(video_titles))
        )

        payload = {
            "model": self.settings.openrouter_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        try:
            logger.info("=================================================================")
            logger.info("AI MODULE GENERATION - LLM CALL")
            logger.info("Model used: %s", self.settings.openrouter_model)
            logger.info("Prompt payload sent:\n%s", json.dumps(payload, indent=2))
            logger.info("=================================================================")

            with httpx.Client(timeout=45.0) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                res_data = response.json()
                content = res_data["choices"][0]["message"]["content"].strip()

            logger.info("=================================================================")
            logger.info("AI MODULE GENERATION - RAW RESPONSE RECEIVED:\n%s", content)
            logger.info("=================================================================")

            # Clean markdown code blocks if the LLM ignored the system instructions
            if content.startswith("```"):
                lines = content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                content = "\n".join(lines).strip()

            data = json.loads(content)
            # Validate structure
            validated = AIModulesOutput.model_validate(data)
            parsed_data = [m.model_dump() for m in validated.modules]
            logger.info("=================================================================")
            logger.info("AI MODULE GENERATION - PARSED RESPONSE:\n%s", json.dumps(parsed_data, indent=2))
            logger.info("=================================================================")
            logger.info("AI generation successful. Received %d modules.", len(validated.modules))
            return parsed_data

        except BadRequestException:
            raise
        except Exception as exc:
            logger.error("AI service error: %s. Falling back to local module grouping.", exc)
            return self._generate_fallback_modules(roadmap_title, video_titles)

    def _generate_fallback_modules(
        self,
        roadmap_title: str,
        video_titles: list[str],
    ) -> list[dict]:
        """
        Fallback generator that partitions video titles into three modules.
        Guarantees that the app remains functional even during API or network failures.
        """
        total = len(video_titles)
        if total == 0:
            return []

        # Simple split into 3 chunks
        chunk_size = max(1, total // 3)
        modules = []

        m1_v = list(range(0, min(chunk_size, total)))
        if m1_v:
            modules.append({
                "name": f"{roadmap_title} Fundamentals",
                "description": f"Introduction to the core concepts of {roadmap_title}.",
                "video_positions": m1_v,
            })

        m2_v = list(range(min(chunk_size, total), min(chunk_size * 2, total)))
        if m2_v:
            modules.append({
                "name": f"Intermediate {roadmap_title} Concepts",
                "description": "Building hands-on experience and working with core patterns.",
                "video_positions": m2_v,
            })

        m3_v = list(range(min(chunk_size * 2, total), total))
        if m3_v:
            modules.append({
                "name": f"Advanced {roadmap_title} Topics",
                "description": "Wrapping up the curriculum with advanced tools and final topics.",
                "video_positions": m3_v,
            })

        logger.info("Fallback generation created %d modules for %r", len(modules), roadmap_title)
        return modules

    def generate_learning_insights(
        self,
        roadmap_title: str,
        modules_summary: list[dict],
        completed_videos: list[dict],
    ) -> dict:
        """
        Calls OpenRouter to generate study insights, strengths, weak areas,
        and recommendations based on user's progress and notes.
        """
        if not self.settings.openrouter_api_key:
            logger.warning("OPENROUTER_API_KEY is empty. Real AI insights generation cannot proceed.")
            raise BadRequestException(
                "OpenRouter API key is missing. Please set OPENROUTER_API_KEY in your backend .env file."
            )

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.frontend_url,
            "X-Title": "SkillMap AI",
        }

        system_prompt = (
            "You are an expert personal learning assistant, study mentor, and academic advisor.\n"
            "Your task is to analyze a student's progress through a learning roadmap and generate personalized study insights.\n\n"
            "You will be given the roadmap title, a list of modules with progress (completed/total videos), "
            "and details of recently completed videos (including the student's study notes, if any).\n\n"
            "You must return a JSON object that strictly conforms to the following schema:\n"
            "{\n"
            "  \"summary\": \"A high-level encouraging progress summary (2-3 sentences) describing their current learning status.\",\n"
            "  \"strengths\": [\"Strength bullet point 1 (based on completed topics/notes)\", \"Strength bullet point 2\"],\n"
            "  \"weak_areas\": [\"Topic/concept to review (based on partially completed modules, missing concepts, or notes)\", \"Review point 2\"],\n"
            "  \"recommended_next_module\": \"Name of the specific module they should focus on next\",\n"
            "  \"estimated_completion_days\": 4,\n"
            "  \"study_recommendation\": \"A concrete, actionable study tip or strategy (1-2 sentences) to help them study more effectively.\"\n"
            "}\n\n"
            "Guidelines:\n"
            "1. Provide encouraging, supportive, but objective feedback.\n"
            "2. Tailor strengths and weak areas to the specific topics in the modules. If user notes are provided, analyze them to detect if the student grasped key concepts or left queries.\n"
            "3. If no videos are completed yet, list 'Getting started with the first module' under weak areas and keep strengths empty or generic.\n"
            "4. estimated_completion_days must be a reasonable positive integer representing days left. If 100% complete, it should be 0.\n"
            "5. Output ONLY valid, raw JSON. Do not wrap it in markdown code blocks."
        )

        # Build user content
        modules_text = []
        for m in modules_summary:
            comp = m.get("completed_count", 0)
            tot = m.get("total_count", 0)
            modules_text.append(f"- Module: {m['name']} (Progress: {comp}/{tot} videos)\n  Description: {m.get('description', '')}")

        completed_videos_text = []
        for v in completed_videos:
            notes = v.get("user_notes") or "No notes provided."
            completed_videos_text.append(f"- Video: {v['title']}\n  Student Notes: {notes}")

        user_content = (
            f"Roadmap Title: {roadmap_title}\n\n"
            f"Modules Progress:\n" + "\n".join(modules_text) + "\n\n"
            f"Student's Completed Videos & Notes:\n" + ("\n".join(completed_videos_text) if completed_videos_text else "No videos completed yet.")
        )

        payload = {
            "model": self.settings.openrouter_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        try:
            logger.info("=================================================================")
            logger.info("AI LEARNING INSIGHTS - LLM CALL")
            logger.info("Model used: %s", self.settings.openrouter_model)
            logger.info("Prompt payload sent:\n%s", json.dumps(payload, indent=2))
            logger.info("=================================================================")

            with httpx.Client(timeout=45.0) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                res_data = response.json()
                content = res_data["choices"][0]["message"]["content"].strip()

            logger.info("=================================================================")
            logger.info("AI LEARNING INSIGHTS - RAW RESPONSE RECEIVED:\n%s", content)
            logger.info("=================================================================")

            # Clean markdown code blocks if the LLM ignored instructions
            if content.startswith("```"):
                lines = content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                content = "\n".join(lines).strip()

            data = json.loads(content)
            # Basic key validation and coercion to keep it robust
            validated = {
                "summary": str(data.get("summary", "Keep up the good work! You are making steady progress.")),
                "strengths": list(data.get("strengths", [])),
                "weak_areas": list(data.get("weak_areas", [])),
                "recommended_next_module": str(data.get("recommended_next_module", "")),
                "estimated_completion_days": int(data.get("estimated_completion_days", 5)),
                "study_recommendation": str(data.get("study_recommendation", "Try blocking out 30 minutes a day to stay consistent.")),
            }
            logger.info("=================================================================")
            logger.info("AI LEARNING INSIGHTS - PARSED RESPONSE:\n%s", json.dumps(validated, indent=2))
            logger.info("=================================================================")
            return validated

        except BadRequestException:
            raise
        except Exception as exc:
            logger.error("AI insights service error: %s. Falling back to programmatic insights.", exc)
            return self._generate_fallback_insights(roadmap_title, modules_summary, completed_videos)

    def _generate_fallback_insights(
        self,
        roadmap_title: str,
        modules_summary: list[dict],
        completed_videos: list[dict],
    ) -> dict:
        """
        Generate fallback study insights programmatically based on the student's progress.
        """
        total_completed = 0
        total_videos = 0
        first_incomplete_module = None

        for m in modules_summary:
            comp = m.get("completed_count", 0)
            tot = m.get("total_count", 0)
            total_completed += comp
            total_videos += tot
            if comp < tot and first_incomplete_module is None:
                first_incomplete_module = m["name"]

        # Calculate percentage
        pct = (total_completed / total_videos * 100) if total_videos > 0 else 0

        # Basic default values
        summary = ""
        strengths = []
        weak_areas = []
        recommended_next_module = first_incomplete_module or "Roadmap Completed!"
        estimated_completion_days = max(1, (total_videos - total_completed) // 2) if pct < 100 else 0
        study_recommendation = ""

        if pct == 0:
            summary = f"You haven't started the '{roadmap_title}' roadmap yet. Take the first step today to start building your skills!"
            strengths = []
            weak_areas = ["Getting started with the first modules."]
            study_recommendation = "Try blocking out just 15 minutes today to watch the first video and write down a quick summary."
        elif pct < 50:
            summary = f"You have started '{roadmap_title}' and completed {total_completed} of {total_videos} videos ({pct:.0f}%). You are building consistency!"
            strengths = ["Getting started and taking the initiative to learn core topics."]
            weak_areas = ["Completing the fundamental sections to build a solid base."]
            study_recommendation = "Aim to complete 1-2 videos per session, and write down 2 bullet points of key takeaways for each video."
        elif pct < 100:
            summary = f"You are more than halfway through '{roadmap_title}'! You've finished {total_completed} of {total_videos} videos ({pct:.0f}%). Great progress!"
            strengths = ["Demonstrated persistence in working through intermediate subjects.", "Good study routine."]
            weak_areas = ["Mastering the remaining advanced lessons in the roadmap."]
            study_recommendation = "Review the concepts in your completed modules before taking on the final advanced modules."
        else:
            summary = f"Congratulations! You completed the entire '{roadmap_title}' roadmap ({total_completed}/{total_videos} videos). That's a fantastic achievement!"
            strengths = ["Outstanding completion rate.", "Broad knowledge across all modules.", "High consistency."]
            weak_areas = []
            study_recommendation = "Great job! Try importing a new playlist or start working on a personal project to apply what you've learned."

        return {
            "summary": summary,
            "strengths": strengths,
            "weak_areas": weak_areas,
            "recommended_next_module": recommended_next_module,
            "estimated_completion_days": estimated_completion_days,
            "study_recommendation": study_recommendation,
        }

    # ─────────────────────────────────────────────────────────────
    # Video Notes Generation
    # ─────────────────────────────────────────────────────────────

    def generate_video_notes(
        self,
        video_title: str,
        roadmap_title: str,
        module_name: str | None = None,
        video_description: str | None = None,
    ) -> dict:
        """
        Call OpenRouter to generate structured study notes for a single video.

        Input context:
          video_title       — the YouTube video title
          roadmap_title     — parent playlist / roadmap title (provides curriculum context)
          module_name       — which learning module this video belongs to (optional)
          video_description — YouTube description (optional; trimmed to 500 chars)

        Returns a dict with keys:
          summary, key_concepts, important_terms, interview_questions

        Falls back to local generation if the API is unavailable.
        """
        if not self.settings.openrouter_api_key:
            logger.warning(
                "OPENROUTER_API_KEY is empty. Real AI notes generation cannot proceed."
            )
            raise BadRequestException(
                "OpenRouter API key is missing. Please set OPENROUTER_API_KEY in your backend .env file."
            )

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.frontend_url,
            "X-Title": "SkillMap AI",
        }

        system_prompt = (
            "You are an expert educator and study assistant.\n"
            "Your task is to generate structured, concise study notes for a single educational video.\n\n"
            "You will be given the video title, its parent learning roadmap, optionally the module it "
            "belongs to, and optionally its description. Use these to infer what the video teaches.\n\n"
            "You must return a JSON object that strictly conforms to the following schema:\n"
            "{\n"
            "  \"summary\": \"A clear 2-4 sentence overview of what the video covers and why it matters.\",\n"
            "  \"key_concepts\": [\n"
            "    \"First key concept or skill taught in this video\",\n"
            "    \"Second key concept\"\n"
            "  ],\n"
            "  \"important_terms\": [\n"
            "    \"Term or keyword: Brief definition\",\n"
            "    \"Another term: Its definition\"\n"
            "  ],\n"
            "  \"interview_questions\": [\n"
            "    \"A question a technical interviewer might ask about this topic?\",\n"
            "    \"Another potential interview question?\"\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "1. Provide 3-6 key_concepts as short, actionable phrases (not sentences).\n"
            "2. Provide 3-5 important_terms in 'Term: Definition' format.\n"
            "3. Provide 3-5 interview_questions that test genuine understanding of the topic.\n"
            "4. Keep the summary factual and educational — do not mention the video format or presenter.\n"
            "5. Tailor all content specifically to the video title and roadmap context.\n"
            "6. Output ONLY valid, raw JSON. Do not wrap in markdown code blocks. Do not include explanations."
        )

        # Build the user content with all available context
        context_lines = [f"Video Title: {video_title}", f"Roadmap / Course: {roadmap_title}"]
        if module_name:
            context_lines.append(f"Module: {module_name}")
        if video_description:
            # Trim description to 500 chars to keep prompt focused
            trimmed_desc = video_description[:500].strip()
            if trimmed_desc:
                context_lines.append(f"Video Description: {trimmed_desc}")

        user_content = "\n".join(context_lines)

        payload = {
            "model": self.settings.openrouter_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
        }

        try:
            logger.info("=================================================================")
            logger.info("AI VIDEO NOTES - LLM CALL")
            logger.info("Model used: %s", self.settings.openrouter_model)
            logger.info("Video: %r | Roadmap: %r | Module: %r", video_title, roadmap_title, module_name)
            logger.info("Prompt payload sent:\n%s", json.dumps(payload, indent=2))
            logger.info("=================================================================")

            with httpx.Client(timeout=45.0) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                res_data = response.json()
                content = res_data["choices"][0]["message"]["content"].strip()

            logger.info("=================================================================")
            logger.info("AI VIDEO NOTES - RAW RESPONSE RECEIVED:\n%s", content)
            logger.info("=================================================================")

            # Strip markdown code fences if the model wrapped the JSON anyway
            if content.startswith("```"):
                lines = content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                content = "\n".join(lines).strip()

            data = json.loads(content)

            # Validate and coerce each field to ensure consistent shape
            validated = {
                "summary": str(data.get("summary", "")).strip(),
                "key_concepts": [str(c) for c in data.get("key_concepts", []) if c],
                "important_terms": [str(t) for t in data.get("important_terms", []) if t],
                "interview_questions": [str(q) for q in data.get("interview_questions", []) if q],
            }

            logger.info("=================================================================")
            logger.info("AI VIDEO NOTES - PARSED RESPONSE:\n%s", json.dumps(validated, indent=2))
            logger.info("=================================================================")
            logger.info(
                "Video notes generated successfully: %d concepts, %d terms, %d questions.",
                len(validated["key_concepts"]),
                len(validated["important_terms"]),
                len(validated["interview_questions"]),
            )
            return validated

        except BadRequestException:
            raise
        except Exception as exc:
            logger.error(
                "AI video notes service error: %s. Falling back to generic notes.", exc
            )
            return self._generate_fallback_notes(video_title, roadmap_title)

    def _generate_fallback_notes(
        self,
        video_title: str,
        roadmap_title: str,
    ) -> dict:
        """
        Generate deterministic placeholder notes when the AI API is unavailable.
        Keeps the app functional and gives the user useful structure to fill in.
        """
        logger.info(
            "Fallback notes generated for video %r in roadmap %r", video_title, roadmap_title
        )
        return {
            "summary": (
                f"This video covers topics related to '{video_title}' as part of the "
                f"'{roadmap_title}' learning roadmap. Watch the video and add your own notes."
            ),
            "key_concepts": [
                f"Core topic: {video_title}",
                "Review the main ideas presented in the video",
                "Apply concepts with hands-on practice",
            ],
            "important_terms": [
                f"{roadmap_title}: The subject area this video belongs to",
                "Concept: A fundamental idea covered in this lesson",
            ],
            "interview_questions": [
                f"Can you explain the main concept covered in '{video_title}'?",
                "How would you apply what you learned in a real-world scenario?",
                "What are the most important things to remember from this lesson?",
            ],
        }

