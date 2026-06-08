export default function NotFound() {
  return (
    <div className="max-w-xl mx-auto px-4 py-24 text-center">
      <div className="text-6xl font-bold text-gray-200 mb-4">404</div>
      <h1 className="text-xl font-semibold text-gray-700 mb-2">Page not found</h1>
      <p className="text-gray-500 mb-6">The audit or page you're looking for doesn't exist.</p>
      <a href="/" className="text-brand-accent hover:underline text-sm font-medium">← Back to Sentinel</a>
    </div>
  );
}
