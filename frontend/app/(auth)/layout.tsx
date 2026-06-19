export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div style={{ position: 'relative', minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      {/* Ambient background glows */}
      <div className="auth-bg" aria-hidden="true" />
      {/* Content */}
      <div style={{ position: 'relative', zIndex: 1, width: '100%', padding: '1.5rem' }}>
        {children}
      </div>
    </div>
  );
}
