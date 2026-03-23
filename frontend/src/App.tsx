import { useEffect, useState } from "react";
import { Nav }            from "./components/Nav";
import { Landing }        from "./features/landing/Landing";
import { Login }          from "./features/auth/Login";
import { ResetPassword }  from "./features/auth/ResetPassword";
import { Dashboard }      from "./features/dashboard/Dashboard";
import { CaseFlow }       from "./features/case/CaseFlow";
import { DossierScreen }  from "./features/dossier/DossierScreen";
import { Preise }         from "./features/pricing/Preise";
import { usePageState }   from "./hooks/usePageState";
import { authApi }        from "./services/api";
import { colors }        from "./theme/tokens";
import type { Page }      from "./types";

// ─────────────────────────────────────────────────────────────────────────────
// App — root component
//
// Navigation is intentionally managed via a simple useState hook.
// When migrating to a real router, replace usePageState() with
// React Router's <Routes> / <Route> and useNavigate().
// ─────────────────────────────────────────────────────────────────────────────

const SCREENS: Record<Page, (props: { setPage: (p: Page) => void; setLoggedIn?: (v: boolean) => void }) => JSX.Element> = {
  landing:        ({ setPage })              => <Landing        setPage={setPage} />,
  login:          ({ setPage, setLoggedIn }) => <Login          setPage={setPage} setLoggedIn={setLoggedIn!} />,
  "reset-password": ({ setPage })            => <ResetPassword  setPage={setPage} />,
  dashboard:      ({ setPage })              => <Dashboard      setPage={setPage} />,
  case:           ({ setPage })              => <CaseFlow       setPage={setPage} />,
  dossier:        ({ setPage })              => <DossierScreen  setPage={setPage} />,
  preise:         ({ setPage })              => <Preise         setPage={setPage} />,
  hilfe:          ({ setPage })              => <Landing        setPage={setPage} />,
};

// Seiten, auf die ein eingeloggter Nutzer beim Start nicht landen soll
const REDIRECT_ON_AUTH: Page[] = ["landing", "login"];

export default function App() {
  const { page, setPage, loggedIn, setLoggedIn } = usePageState("landing");

  // authChecking: true solange der /me-Check noch läuft.
  // Verhindert kurzes Aufblitzen der Landingpage bei eingeloggten Nutzern.
  const [authChecking, setAuthChecking] = useState(
    // Kein Check nötig wenn wir direkt auf reset-password sind (Token in URL)
    page !== "reset-password",
  );

  useEffect(() => {
    if (page === "reset-password") return; // Reset-Flow braucht keinen Session-Check

    authApi.me()
      .then(() => {
        setLoggedIn(true);
        if (REDIRECT_ON_AUTH.includes(page)) setPage("dashboard");
      })
      .catch(() => {
        setLoggedIn(false);
      })
      .finally(() => {
        setAuthChecking(false);
      });
  }, []); // einmalig beim Mount — page ist durch Closure korrekt erfasst

  const Screen = SCREENS[page] ?? SCREENS.landing;

  if (authChecking) {
    return (
      <div style={{ minHeight: "100vh", background: colors.bg, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <span style={{ fontFamily: "'Plus Jakarta Sans', sans-serif", fontSize: 14, color: colors.muted }}>
          Laden…
        </span>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: colors.bg }}>
      <Nav page={page} setPage={setPage} loggedIn={loggedIn} />
      <main>
        <Screen setPage={setPage} setLoggedIn={setLoggedIn} />
      </main>
    </div>
  );
}
