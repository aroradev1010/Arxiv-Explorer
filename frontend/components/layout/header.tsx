"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, Menu } from "lucide-react";
import { useState } from "react";
import { Button } from "../ui/button";
import { Sheet } from "../ui/sheet";
const links = [
  ["/search", "Search"],
  ["/compare", "Compare"],
  ["/evaluation", "Evaluation"],
];
export function Header() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const navigation = (
    <nav aria-label="Main navigation">
      {links.map(([href, label]) => (
        <Link
          key={href}
          href={href}
          aria-current={pathname === href ? "page" : undefined}
          onClick={() => setOpen(false)}
          className={pathname === href ? "nav-link active" : "nav-link"}
        >
          {label}
        </Link>
      ))}
    </nav>
  );
  return (
    <header className="app-header">
      <div className="container flex h-20 items-center justify-between gap-4">
        <Link href="/" className="brand">
          <span className="brand-icon">
            <BookOpen size={21} />
          </span>
          <span>
            arXiv <strong>explorer</strong>
          </span>
        </Link>
        <div className="hidden md:block">{navigation}</div>
        <div className="flex items-center gap-2">
          <div className="md:hidden">
            <Sheet
              title="Navigation"
              open={open}
              onOpenChange={setOpen}
              trigger={
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label="Open navigation"
                >
                  <Menu size={20} />
                </Button>
              }
            >
              {navigation}
            </Sheet>
          </div>
        </div>
      </div>
    </header>
  );
}
