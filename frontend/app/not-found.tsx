import Link from "next/link";

export default function NotFound() {
  return <section className="not-found"><div><h1>Page not found</h1><p>The page you are looking for does not exist.</p><Link className="button-primary" href="/">Return home</Link></div></section>;
}
