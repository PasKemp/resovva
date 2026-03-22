import { Nav }           from "./components/Nav";
import { Landing }       from "./features/landing/Landing";
import { Login }         from "./features/auth/Login";
import { Dashboard }     from "./features/dashboard/Dashboard";
import { CaseFlow }      from "./features/case/CaseFlow";
import { DossierScreen } from "./features/dossier/DossierScreen";
import { Preise }        from "./features/pricing/Preise";
import { usePageState }  from "./hooks/usePageState";
import { colors }        from "./theme/tokens";
import type { Page }     from "./types";

// ─────────────────────────────────────────────────────────────────────────────
// App — root component
//
// Navigation is intentionally managed via a simple useState hook.
// When migrating to a real router, replace usePageState() with
// React Router's <Routes> / <Route> and useNavigate().
// ─────────────────────────────────────────────────────────────────────────────

const SCREENS: Record<Page, (props: { setPage: (p: Page) => void; setLoggedIn?: (v: boolean) => void }) => JSX.Element> = {
  landing:   ({ setPage })                    => <Landing       setPage={setPage} />,
  login:     ({ setPage, setLoggedIn })       => <Login         setPage={setPage} setLoggedIn={setLoggedIn!} />,
  dashboard: ({ setPage })                    => <Dashboard     setPage={setPage} />,
  case:      ({ setPage })                    => <CaseFlow      setPage={setPage} />,
  dossier:   ({ setPage })                    => <DossierScreen setPage={setPage} />,
  preise:    ({ setPage })                    => <Preise        setPage={setPage} />,
  hilfe:     ({ setPage })                    => <Landing       setPage={setPage} />,
};

export default function App() {
  const { page, setPage, loggedIn, setLoggedIn } = usePageState("landing");

  const Screen = SCREENS[page] ?? SCREENS.landing;

  return (
    <div style={{ minHeight: "100vh", background: colors.bg }}>
      <Nav page={page} setPage={setPage} loggedIn={loggedIn} />
      <main>
        <Screen setPage={setPage} setLoggedIn={setLoggedIn} />
      </main>
    </div>
  );
}
