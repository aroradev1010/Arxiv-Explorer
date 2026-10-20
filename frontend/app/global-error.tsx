"use client";
export default function GlobalError({ retry }: { retry: () => void }) {
  return (
    <html lang="en">
      <body>
        <main
          style={{
            fontFamily: "Arial, sans-serif",
            padding: "3rem",
            maxWidth: "45rem",
            margin: "auto",
          }}
        >
          <h1>Unable to display ArXiv Explorer</h1>
          <p>Try loading the application again.</p>
          <button onClick={retry}>Retry</button>
        </main>
      </body>
    </html>
  );
}
