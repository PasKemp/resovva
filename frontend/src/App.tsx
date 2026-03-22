import { CssBaseline, Typography, Container } from "@mui/material";

export default function App() {
  return (
    <>
      <CssBaseline />
      <Container maxWidth="sm" sx={{ py: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Resovva
        </Typography>
        <Typography color="text.secondary">Frontend-Platzhalter (Vite + React + MUI)</Typography>
      </Container>
    </>
  );
}
