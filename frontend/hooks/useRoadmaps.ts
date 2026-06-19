'use client';

import { useState, useEffect, useCallback } from 'react';
import { roadmapsApi } from '@/lib/api';
import type { RoadmapSummary } from '@/types';

export function useRoadmaps() {
  const [roadmaps, setRoadmaps] = useState<RoadmapSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await roadmapsApi.list();
      setRoadmaps(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load roadmaps');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    roadmapsApi.list()
      .then((data) => {
        if (active) {
          setRoadmaps(data);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (active) {
          setError(err instanceof Error ? err.message : 'Failed to load roadmaps');
          setIsLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  return { roadmaps, isLoading, error, refetch };
}
