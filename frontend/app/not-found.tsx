import Link from "next/link";
export default function NotFound() {
  return (
    <div className="state">
      <h1>Page not found</h1>
      <p>Continue exploring the research collection.</p>
      <Link href="/search">Back to search</Link>
    </div>
  );
}
