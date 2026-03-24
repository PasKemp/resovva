import { useEffect, useState } from "react";
import { Nav }               from "./components/Nav";
import { Landing }           from "./features/landing/Landing";
import { Login }             from "./features/auth/Login";
import { ResetPassword }     from "./features/auth/ResetPassword";
import { CompleteProfile }   from "./features/auth/CompleteProfile";
import { Dashboard }         from "./features/dashboard/Dashboard";
import { CaseFlow }          from "./features/case/CaseFlow";
import { DossierScreen }     from "./features/dossier/DossierScreen";
import { Preise }            from "./features/pricing/Preise";
import { ProfilePage }       from "./features/profile/ProfilePage";
import { MobileUploadPage }  from "./features/mobile/MobileUploadPage";
import { usePageState }      from "./hooks/usePageState";
import { authApi }           from "./services/api";
import { colors }            from "./theme/tokens";
import type { Page }         from "./types";

// Seiten ohne Login-Zwang (oder die selbst den Auth-Status prüfen)
const NO_AUTH_PAGES: Page[] = ["reset-password", "mobile-upload", "complete-profile"];
// Seiten auf die ein eingeloggter Nutzer beim Start nicht landen soll
const REDIRECT_ON_AUTH: Page[] = ["landing", "login"];

export default function App() {
  const { page, setPage, loggedIn, setLoggedIn } = usePageState("landing");
  const [authChecking, setAuthChecking] = useState(!NO_AUTH_PAGES.includes(page));
  // Aktive Fall-ID: undefined = neuer Fall anlegen, string = bestehenden Fall öffnen
  const [activeCaseId,   setActiveCaseId]   = useState<string | undefined>();
  // Step-Persistenz: beim Zurück zur Übersicht und erneutem Öffnen gleicher Fall → selber Schritt
  const [activeCaseStep, setActiveCaseStep] = useState<number>(0);

  const handleLogout = async () => {
    try { await authApi.logout(); } finally {
      setLoggedIn(false);
      setPage("landing");
    }
  };

  // Navigiert zum CaseFlow – mit bestehender ID (öffnen) oder ohne (neu anlegen)
  const openCase = (caseId?: string) => {
    // Neuer oder anderer Fall → Step zurücksetzen; selber Fall → Step beibehalten
    if (caseId !== activeCaseId) setActiveCaseStep(0);
    setActiveCaseId(caseId);
    setPage("case");
  };

  useEffect(() => {
    if (NO_AUTH_PAGES.includes(page)) return;

    authApi.me()
      .then((user) => {
        setLoggedIn(true);
        if (REDIRECT_ON_AUTH.includes(page)) {
          if (!user.profile_complete) {
            setPage("complete-profile");
          } else {
            setPage("dashboard");
          }
        }
      })
      .catch(() => setLoggedIn(false))
      .finally(() => setAuthChecking(false));
  }, []);

  // Standalone-Seiten ohne Nav
  if (page === "mobile-upload") return <MobileUploadPage />;

  if (authChecking) {
    return (
      <div style={{ minHeight: "100vh", background: colors.bg, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <span style={{ fontFamily: "'Plus Jakarta Sans', sans-serif", fontSize: 14, color: colors.muted }}>
          Laden…
        </span>
      </div>
    );
  }

  const renderScreen = () => {
    switch (page) {
      case "landing":           return <Landing         setPage={setPage} />;
      case "login":             return <Login           setPage={setPage} setLoggedIn={setLoggedIn} />;
      case "reset-password":    return <ResetPassword   setPage={setPage} />;
      case "complete-profile":  return <CompleteProfile setPage={setPage} />;
      case "dashboard":         return <Dashboard       setPage={setPage} openCase={openCase} />;
      case "case":              return <CaseFlow        setPage={setPage} caseId={activeCaseId} initialStep={activeCaseStep} onStepChange={setActiveCaseStep} onCaseCreated={setActiveCaseId} />;
      case "dossier":           return <DossierScreen   setPage={setPage} />;
      case "preise":            return <Preise          setPage={setPage} />;
      case "hilfe":             return <Landing         setPage={setPage} />;
      case "profile":           return <ProfilePage     setPage={setPage} />;
      default:                  return <Landing         setPage={setPage} />;
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: colors.bg }}>
      <Nav page={page} setPage={setPage} loggedIn={loggedIn} onLogout={handleLogout} />
      <main>{renderScreen()}</main>
    </div>
  );
}
