import Link from "next/link";
export function Footer() {
  return (
    <footer>
      <div className="container flex flex-wrap justify-between gap-5">
        <div>
          <strong>ArXiv Explorer</strong>
          <p>A local research corpus. Metadata sourced from arXiv.</p>
          <p>An independent academic project; not affiliated with arXiv.</p>
        </div>
        <div className="flex gap-6">
          <Link href="/about">Methodology</Link>
          <a href="https://arxiv.org" target="_blank" rel="noopener noreferrer">
            arXiv ↗
          </a>
        </div>
      </div>
    </footer>
  );
}
