import React, { lazy, Suspense } from "react";

const DemoConfigurator = lazy(() => import("./pages/DemoConfigurator"));
const NormalApp = lazy(() => import("./AppNormal"));

class RootErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error) {
    console.error("Auto AI root route error", error);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div
        style={{
          minHeight: "100vh",
          display: "grid",
          placeItems: "center",
          padding: 24,
          background: "#050505",
          color: "#fff",
          fontFamily: "system-ui, sans-serif",
          textAlign: "center",
        }}
      >
        <div style={{ maxWidth: 620 }}>
          <div
            style={{
              fontSize: 11,
              letterSpacing: ".2em",
              textTransform: "uppercase",
              color: "#f59e0b",
              marginBottom: 12,
            }}
          >
            Auto AI India · Demo diagnostic
          </div>
          <h1 style={{ fontSize: 24, fontWeight: 500, margin: "0 0 10px" }}>
            The demo module failed to load
          </h1>
          <p style={{ color: "rgba(255,255,255,.6)", lineHeight: 1.6, margin: 0 }}>
            The page shell loaded, but the browser rejected the 3D demo bundle.
            Open the browser console for the underlying error.
          </p>
          <pre
            style={{
              marginTop: 18,
              padding: 14,
              borderRadius: 12,
              background: "#111",
              border: "1px solid rgba(255,255,255,.1)",
              color: "#fca5a5",
              fontSize: 11,
              lineHeight: 1.5,
              overflow: "auto",
              textAlign: "left",
              whiteSpace: "pre-wrap",
            }}
          >
            {String(this.state.error?.message || this.state.error)}
          </pre>
        </div>
      </div>
    );
  }
}

function Loading({ demo }) {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        background: "#050505",
        color: "rgba(255,255,255,.7)",
        fontFamily: "system-ui, sans-serif",
        letterSpacing: ".12em",
        textTransform: "uppercase",
        fontSize: 11,
      }}
    >
      Loading {demo ? "3D demonstrator" : "Auto AI India"}…
    </div>
  );
}

export default function App() {
  const isDemo =
    typeof window !== "undefined" &&
    window.location.pathname.replace(/\/+$/, "") === "/configurator-demo";

  return (
    <RootErrorBoundary>
      <Suspense fallback={<Loading demo={isDemo} />}>
        {isDemo ? <DemoConfigurator /> : <NormalApp />}
      </Suspense>
    </RootErrorBoundary>
  );
}
