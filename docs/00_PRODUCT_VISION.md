# 00. Product Vision & MVP Scope: Resovva.ai

---

## Inhaltsverzeichnis

1. [Executive Summary](#1-executive-summary)
2. [MVP Definition (P0 Scope)](#2-mvp-definition-p0-scope)
3. [Technische Leitplanken](#3-technische-leitplanken)

---

## 1. Executive Summary

Resovva.ai ist ein "Intelligenter Fall-Assistent" (LegalTech), der Endverbrauchern hilft, Streitigkeiten mit Stromanbietern/Netzbetreibern zu strukturieren. Wir verkaufen keine Rechtsberatung, sondern **Ordnung und Waffengleichheit**.

- **Preismodell:** 20€ Pay-per-Case.
- **USP:** Der "Rote Faden" (Automatisierte Chronologie & Beweisführung).

## 2. MVP Definition (P0 Scope)

Wir bauen einen linearen Wizard, keinen offenen Chatbot.

### IN SCOPE (Must Haves)

- **Input:** Upload von PDF (Rechnungen/Verträge) & E-Mail-Exporten (.msg/.eml).
- **Processing:**
  - OCR & Text-Extraktion.
  - LLM-basierte Entitäten-Erkennung (MaLo, Zählernummer, Beträge).
  - Automatische Erstellung einer Chronologie (Timeline).
  - Gap-Analysis: Gezieltes Nachfragen bei fehlenden Belegen.
- **Output:** Generierung eines PDF-Dossiers (Sachverhalt + Beweismittel-Anhang).
- **Auth:** "Magic Link" via E-Mail. Keine Passwörter.

### OUT OF SCOPE (Für V1)

- Direkte API-Anbindung an Behörden/Schlichtungsstellen.
- Vollautomatischer, offener Chat-Dialog ("Frag mich alles").
- Nutzerkonten mit Passwort-Management.
- Komplexe juristische Datenbank (RAG nur auf User-Docs).

## 3. Technische Leitplanken

- **Stack:** Python 3.12, FastAPI, LangChain/LangGraph, Qdrant.
- **Privacy:** PII Masking (IBAN/Namen) in der Vorschau. Löschung aller Daten nach 30 Tagen Inaktivität.
- **Architektur:** "Two-Pass" Ansatz (Erst Strukturieren, dann Generieren). Kein Over-Engineering bei K8s für den Start.
