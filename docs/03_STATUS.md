# 📊 HealthLedger Pi — Projektstatus

**Last Updated:** 2026-02-20 (Session 01 — Konzept & Repo-Erstellung)  
**Phase:** 🟡 KONZEPT

---

## 🎯 Aktueller Sprint

**Sprint 1 — Konzept & Fundament**

| Task | Status | Notizen |
|------|--------|---------|
| Konzept ausarbeiten | ✅ DONE | 01_CONCEPT.md |
| GitHub Repo erstellen | ✅ DONE | zentis666/healthledger-pi |
| README | ✅ DONE | Mit Marktanalyse |
| Roadmap | ✅ DONE | 02_ROADMAP.md |
| Marktrecherche | 🟡 TODO | Welche Lösungen gibt es 2026? |
| Tech Spec | 🟡 TODO | DB Schema, API-Design |
| MVP Backend | 🔴 BLOCKED | Wartet auf Spec |

---

## 🔗 Repository

**GitHub:** https://github.com/zentis666/healthledger-pi  
**Basis-Architektur:** Aufbauend auf PiAgent (apps/piagent in ai-nas-project)

---

## 💡 Key Decisions

- **Stack:** Python/FastAPI + SQLite + PWA (bewährt von PiAgent)
- **Verschlüsselung:** SQLCipher + age (Phase 2, nicht Phase 1)
- **KI:** Ollama auf AI-NAS (kein separates Modell auf Pi nötig)
- **Zugang:** Tailscale VPN (bereits vorhanden)

---

## 📋 Nächste Schritte

1. Marktrecherche: Was gibt es 2026 an Health-Apps?
2. DB Schema designen
3. PiAgent-Code als Basis nehmen → erweitern
4. Phase 1 MVP starten
