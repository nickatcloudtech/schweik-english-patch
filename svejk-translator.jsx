import React, { useState, useRef, useCallback, useEffect, useMemo } from "react";
import Papa from "papaparse";

/* ------------------------------------------------------------------ */
/*  Švejk Dialogue Translator — human RU→EN, Hašek deadpan preserved   */
/* ------------------------------------------------------------------ */

const STORAGE_PREFIX = "svejk-translator:";
const PAGE_SIZE = 25;

const LOCATION_GLOSS = {
  "Трактир У чаши": "The Chalice pub",
  "Квартира Лукаша": "Lieutenant Lukáš's flat",
  "Кухня Швейка": "Švejk's kitchen",
  "Гостиная Каца": "Chaplain Katz's parlour",
  "Парк": "the park",
  "Госпиталь палата": "military hospital ward",
  "Кабинет следователя": "the interrogator's office",
  "Психушка коридор": "madhouse corridor",
  "Палата": "the ward",
  "Площадь": "the town square",
  "Часовня": "the garrison chapel",
  "Камера": "the jail cell",
  "Вход в психушку": "madhouse entrance",
  "Процедурная": "the treatment room",
  "Комната Швейка": "Švejk's room",
  "Вокзал": "the railway station",
  "Комиссариат": "the police commissariat",
  "Комната ПМ": "Mrs Müller's room",
  "Кабинет главврача": "the head doctor's office",
};

const STYLE_SECTIONS = [
  {
    title: "The voice",
    body:
      "Hašek's comedy runs on deadpan earnestness. Švejk says absurd things with total sincerity — never wink at the joke. Bureaucratic and military registers get applied to trivial matters. Pub anecdotes meander: \"I knew a fellow once in Vršovice who…\" Understatement, not exaggeration. Dry humor throughout.",
  },
  {
    title: "Period register (~1914)",
    body:
      "No modern slang or anachronisms — \"okay\", \"guy\", \"cool\" are out. Prefer \"fellow\", \"chap\", \"a man I knew\", \"beg to report\". Contractions are fine in spoken dialogue.",
  },
  {
    title: "Names & phrases",
    body:
      "Švejk, Mrs Müller (Пани Мюллерова), Palivec, Chaplain Katz, Lieutenant Lukáš, Bretschneider, Hradčany, Vršovice, The Chalice (У чаши). \"Осмелюсь доложить\" → \"Humbly report, sir\" (or \"Humbly report\" mid-sentence).",
  },
  {
    title: "Length & UI",
    body:
      "Keep English roughly the same length as Russian — game UI constraint. Preserve punctuation feel: ellipses, exclamations, question marks. Short examine-object barks (\"A candle. It burns.\") stay terse and flat; the flatness is the joke.",
  },
  {
    title: "Examples",
    pairs: [
      {
        ru: "Свечка и свечка. На этой неделе уже три таких ушло.",
        en: "A candle's a candle. Three of them gone this week already.",
      },
      {
        ru: "Вообще днем свечки не жгут. Надо придумать, как оправдать такое расточительство.",
        en: "Nobody burns candles in the daytime. I'll have to think up some way to justify that kind of extravagance.",
      },
      {
        ru: "Помню, жил на Градчанах один мясник, сводил всем желающим бородавки раскаленным ножом. А у одной глупой бабы и вскочи бородавка прямо на верхнем веке! Вот так, бедная, без глаза и осталась.",
        en: "I remember there was a butcher up in Hradčany who'd burn off warts with a red-hot knife for anyone who asked. And one silly woman went and got a wart right on her upper eyelid! And that's how the poor thing was left with one eye.",
      },
    ],
  },
];

/* ---------------------------- helpers ----------------------------- */

function cleanField(value) {
  return (value || "").replace(/\0/g, "").trim();
}

function parseRows(data, fields) {
  return data.map((r, idx) => {
    const ru = cleanField(r.russian);
    const en = cleanField(r.english);
    return {
      i: idx,
      raw: { ...r, russian: ru, english: en },
      ru,
      en,
      character: cleanField(r.character),
      location: cleanField(r.location),
      id: cleanField(r.id),
      voice_file: cleanField(r.voice_file),
      sound_ref: cleanField(r.sound_ref),
      notes: cleanField(r.notes),
    };
  });
}

function countTranslated(rows) {
  return rows.filter((r) => r.ru && r.en).length;
}

function storageKey(fileName) {
  return STORAGE_PREFIX + fileName;
}

function saveToStorage(fileName, rows, fields) {
  if (!fileName || !rows) return;
  const payload = {
    fields,
    rows: rows.map((r) => r.raw),
    savedAt: Date.now(),
  };
  try {
    localStorage.setItem(storageKey(fileName), JSON.stringify(payload));
  } catch {
    /* quota exceeded — download is the backup */
  }
}

function loadFromStorage(fileName) {
  try {
    const raw = localStorage.getItem(storageKey(fileName));
    if (!raw) return null;
    const payload = JSON.parse(raw);
    if (!payload.rows || !payload.fields) return null;
    return payload;
  } catch {
    return null;
  }
}

function matchesFilters(row, filters) {
  if (filters.untranslatedOnly && row.en) return false;
  if (filters.location && row.location !== filters.location) return false;
  if (filters.character && row.character !== filters.character) return false;
  if (filters.query) {
    const q = filters.query.toLowerCase();
    const hay = [row.ru, row.en, row.character, row.location, row.id, row.notes]
      .join(" ")
      .toLowerCase();
    if (!hay.includes(q)) return false;
  }
  return true;
}

function lengthHint(ru, en) {
  const ruLen = ru.length;
  const enLen = en.length;
  if (!ruLen) return { label: "", tone: "neutral" };
  const ratio = enLen / ruLen;
  if (enLen === 0) return { label: `${ruLen} RU chars`, tone: "neutral" };
  if (ratio > 1.35) return { label: `${enLen} / ${ruLen} — long`, tone: "warn" };
  if (ratio < 0.65) return { label: `${enLen} / ${ruLen} — short`, tone: "warn" };
  return { label: `${enLen} / ${ruLen}`, tone: "ok" };
}

/* ----------------------------- app -------------------------------- */

export default function SvejkTranslator() {
  const [rows, setRows] = useState(null);
  const [fields, setFields] = useState([]);
  const [fileName, setFileName] = useState("");
  const [error, setError] = useState("");
  const [savedAt, setSavedAt] = useState(null);
  const [showGuide, setShowGuide] = useState(true);
  const [viewIndex, setViewIndex] = useState(0);
  const [listPage, setListPage] = useState(0);
  const [filters, setFilters] = useState({
    location: "",
    character: "",
    untranslatedOnly: true,
    query: "",
  });
  const [draftEn, setDraftEn] = useState("");
  const [draftNotes, setDraftNotes] = useState("");

  const rowsRef = useRef(null);
  const textareaRef = useRef(null);

  const filtered = useMemo(() => {
    if (!rows) return [];
    return rows.filter((r) => r.ru && matchesFilters(r, filters));
  }, [rows, filters]);

  const total = rows ? rows.length : 0;
  const translated = rows ? countTranslated(rows) : 0;
  const pending = total - translated;
  const pct = total ? Math.round((translated / total) * 100) : 0;

  const current = filtered[viewIndex] || null;
  const listSlice = filtered.slice(listPage * PAGE_SIZE, (listPage + 1) * PAGE_SIZE);
  const listPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));

  const locations = useMemo(() => {
    if (!rows) return [];
    return [...new Set(rows.map((r) => r.location).filter(Boolean))].sort();
  }, [rows]);

  const characters = useMemo(() => {
    if (!rows) return [];
    return [...new Set(rows.map((r) => r.character).filter(Boolean))].sort();
  }, [rows]);

  const syncDraft = useCallback((row) => {
    if (!row) {
      setDraftEn("");
      setDraftNotes("");
      return;
    }
    setDraftEn(row.en);
    setDraftNotes(row.notes);
  }, []);

  useEffect(() => {
    syncDraft(current);
  }, [current, syncDraft]);

  const applyEdit = useCallback(
    (en, notes) => {
      if (!rowsRef.current || !current) return;
      const next = rowsRef.current.map((r) => {
        if (r.i !== current.i) return r;
        const trimmedEn = en.trim();
        const trimmedNotes = notes.trim();
        return {
          ...r,
          en: trimmedEn,
          notes: trimmedNotes,
          raw: { ...r.raw, english: trimmedEn, notes: trimmedNotes },
        };
      });
      rowsRef.current = next;
      setRows(next);
      saveToStorage(fileName, next, fields);
      setSavedAt(Date.now());
    },
    [current, fileName, fields]
  );

  const goTo = useCallback(
    (index) => {
      if (!filtered.length) return;
      const clamped = Math.max(0, Math.min(index, filtered.length - 1));
      setViewIndex(clamped);
      const page = Math.floor(clamped / PAGE_SIZE);
      if (page !== listPage) setListPage(page);
    },
    [filtered.length, listPage]
  );

  const goNext = useCallback(() => goTo(viewIndex + 1), [goTo, viewIndex]);
  const goPrev = useCallback(() => goTo(viewIndex - 1), [goTo, viewIndex]);

  const goNextUntranslated = useCallback(() => {
    if (!filtered.length) return;
    for (let k = viewIndex + 1; k < filtered.length; k++) {
      if (!filtered[k].en) {
        goTo(k);
        return;
      }
    }
    for (let k = 0; k < viewIndex; k++) {
      if (!filtered[k].en) {
        goTo(k);
        return;
      }
    }
  }, [filtered, viewIndex, goTo]);

  const saveAndNext = useCallback(() => {
    applyEdit(draftEn, draftNotes);
    goNextUntranslated();
  }, [applyEdit, draftEn, draftNotes, goNextUntranslated]);

  /* -------- file load -------- */
  const loadParsed = useCallback((parsed, flds, name, fromStorage) => {
    rowsRef.current = parsed;
    setRows(parsed);
    setFields(flds);
    setFileName(name);
    setViewIndex(0);
    setListPage(0);
    setError("");
    setSavedAt(fromStorage ? Date.now() : null);
    const firstPending = parsed.findIndex((r) => r.ru && !r.en);
    if (firstPending >= 0) {
      const idxInFiltered = parsed
        .filter((r) => r.ru && matchesFilters(r, { untranslatedOnly: true }))
        .findIndex((r) => r.i === firstPending);
      if (idxInFiltered >= 0) setViewIndex(idxInFiltered);
    }
  }, []);

  const handleFile = (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    setError("");
    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: (result) => {
        const flds = result.meta.fields || [];
        if (!flds.includes("russian") || !flds.includes("english")) {
          setError(
            "This file needs 'russian' and 'english' columns. Found: " + flds.join(", ")
          );
          return;
        }
        const parsed = parseRows(result.data, flds);
        const cached = loadFromStorage(file.name);
        if (cached) {
          const merged = parseRows(cached.rows, cached.fields);
          const byId = new Map(merged.map((r) => [r.i, r]));
          const reconciled = parsed.map((r) => byId.get(r.i) || r);
          loadParsed(reconciled, flds, file.name, true);
        } else {
          loadParsed(parsed, flds, file.name, false);
        }
      },
      error: (err) => setError("Could not read the file: " + err.message),
    });
    e.target.value = "";
  };

  const handleFilterChange = (patch) => {
    setFilters((prev) => {
      const next = { ...prev, ...patch };
      return next;
    });
    setViewIndex(0);
    setListPage(0);
  };

  useEffect(() => {
    if (!rows) return;
    if (viewIndex >= filtered.length) {
      setViewIndex(Math.max(0, filtered.length - 1));
    }
  }, [filtered.length, rows, viewIndex]);

  /* -------- keyboard -------- */
  useEffect(() => {
    if (!rows) return;
    const onKey = (e) => {
      const tag = (e.target && e.target.tagName) || "";
      const typing = tag === "TEXTAREA" || tag === "INPUT" || tag === "SELECT";
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        applyEdit(draftEn, draftNotes);
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        saveAndNext();
        return;
      }
      if (typing && tag !== "BODY") return;
      if (e.key === "ArrowRight" || e.key === "j") goNext();
      if (e.key === "ArrowLeft" || e.key === "k") goPrev();
      if (e.key === "n" && !e.ctrlKey && !e.metaKey) goNextUntranslated();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [rows, applyEdit, draftEn, draftNotes, saveAndNext, goNext, goPrev, goNextUntranslated]);

  /* -------- download -------- */
  const download = () => {
    if (!rowsRef.current) return;
    applyEdit(draftEn, draftNotes);
    const data = rowsRef.current.map((r) => r.raw);
    const csv = Papa.unparse(data, { columns: fields });
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = fileName.replace(/\.csv$/i, "") + "_translated.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const clearCache = () => {
    if (fileName) localStorage.removeItem(storageKey(fileName));
    setSavedAt(null);
  };

  const hint = current ? lengthHint(current.ru, draftEn) : { label: "", tone: "neutral" };
  const locationLabel = current
    ? LOCATION_GLOSS[current.location] || current.location
    : "";

  /* ------------------------------ UI ------------------------------ */
  return (
    <div style={S.page}>
      <style>{CSS_TEXT}</style>

      <div style={S.dossier} className="dossier">
        <div style={S.header}>
          <div style={S.headerRule} />
          <div style={S.eyebrow}>PROTOKOLL · LOCALIZATION FILE · RU→EN · BY HAND</div>
          <h1 style={S.title}>The Good Soldier Švejk</h1>
          <div style={S.subtitle}>
            Human translation desk — deadpan Hašek register, one line at a time
          </div>
          <div style={S.headerRule} />
        </div>

        {!rows && (
          <div style={S.intake}>
            <p style={S.intakeText}>
              Upload <code style={S.code}>translation/schweik_dialogue.csv</code>. Fill the{" "}
              <code style={S.code}>english</code> column yourself, with the style guide open
              beside you. Progress auto-saves in this browser; download the CSV when you
              want to share or run <code style={S.code}>import_text.py</code>.
            </p>
            <label style={S.uploadBtn} className="stampable">
              Select CSV file
              <input
                type="file"
                accept=".csv,text/csv"
                onChange={handleFile}
                style={{ display: "none" }}
              />
            </label>
            {error && <div style={S.error}>{error}</div>}
          </div>
        )}

        {rows && (
          <div>
            <div style={S.ledger}>
              <Ledger label="File" value={fileName} />
              <Ledger label="Lines" value={total.toLocaleString()} />
              <Ledger label="Translated" value={translated.toLocaleString()} />
              <Ledger label="Remaining" value={pending.toLocaleString()} />
              <Ledger label="In view" value={filtered.length.toLocaleString()} />
              {savedAt && (
                <Ledger
                  label="Autosaved"
                  value={new Date(savedAt).toLocaleTimeString()}
                />
              )}
            </div>

            <div style={S.progressOuter}>
              <div style={{ ...S.progressInner, width: pct + "%" }} />
              <div style={S.progressLabel}>{pct}%</div>
            </div>

            <div style={S.controls}>
              <button style={S.primaryBtn} onClick={download}>
                Download CSV {pending > 0 ? "(partial)" : ""}
              </button>
              <button style={S.secondaryBtn} onClick={() => applyEdit(draftEn, draftNotes)}>
                Save line
              </button>
              <button style={S.secondaryBtn} onClick={clearCache}>
                Clear browser cache
              </button>
              <label style={S.uploadBtnSmall} className="stampable">
                Open different file
                <input
                  type="file"
                  accept=".csv,text/csv"
                  onChange={handleFile}
                  style={{ display: "none" }}
                />
              </label>
            </div>

            <div style={S.filterBar}>
              <select
                style={S.select}
                value={filters.location}
                onChange={(e) => handleFilterChange({ location: e.target.value })}
              >
                <option value="">All locations</option>
                {locations.map((loc) => (
                  <option key={loc} value={loc}>
                    {LOCATION_GLOSS[loc] ? `${LOCATION_GLOSS[loc]} (${loc})` : loc}
                  </option>
                ))}
              </select>
              <select
                style={S.select}
                value={filters.character}
                onChange={(e) => handleFilterChange({ character: e.target.value })}
              >
                <option value="">All characters</option>
                {characters.map((ch) => (
                  <option key={ch} value={ch}>
                    {ch}
                  </option>
                ))}
              </select>
              <label style={S.checkLabel}>
                <input
                  type="checkbox"
                  checked={filters.untranslatedOnly}
                  onChange={(e) =>
                    handleFilterChange({ untranslatedOnly: e.target.checked })
                  }
                />
                Untranslated only
              </label>
              <input
                style={S.search}
                type="search"
                placeholder="Search Russian, English, notes…"
                value={filters.query}
                onChange={(e) => handleFilterChange({ query: e.target.value })}
              />
            </div>

            <div style={S.workspace}>
              <aside style={S.sidebar}>
                <button
                  style={S.guideToggle}
                  onClick={() => setShowGuide((v) => !v)}
                  type="button"
                >
                  {showGuide ? "Hide" : "Show"} style guide
                </button>
                {showGuide && (
                  <div style={S.guide}>
                    {STYLE_SECTIONS.map((sec) => (
                      <div key={sec.title} style={S.guideSection}>
                        <div style={S.guideTitle}>{sec.title}</div>
                        {sec.body && <p style={S.guideBody}>{sec.body}</p>}
                        {sec.pairs &&
                          sec.pairs.map((p) => (
                            <div key={p.ru.slice(0, 24)} style={S.example}>
                              <div style={S.exampleRu}>{p.ru}</div>
                              <div style={S.exampleEn}>{p.en}</div>
                            </div>
                          ))}
                      </div>
                    ))}
                  </div>
                )}

                <div style={S.listHead}>
                  Lines {listPage * PAGE_SIZE + 1}–
                  {Math.min((listPage + 1) * PAGE_SIZE, filtered.length)} of{" "}
                  {filtered.length}
                </div>
                <div style={S.lineList}>
                  {listSlice.map((row, localIdx) => {
                    const globalIdx = listPage * PAGE_SIZE + localIdx;
                    const active = current && row.i === current.i;
                    return (
                      <button
                        key={row.i}
                        type="button"
                        style={{
                          ...S.lineItem,
                          ...(active ? S.lineItemActive : {}),
                          ...(!row.en ? S.lineItemPending : {}),
                        }}
                        onClick={() => goTo(globalIdx)}
                      >
                        <span style={S.lineItemMeta}>
                          {row.character || "—"} · {row.en ? "done" : "open"}
                        </span>
                        <span style={S.lineItemRu}>{row.ru}</span>
                      </button>
                    );
                  })}
                </div>
                <div style={S.listPager}>
                  <button
                    type="button"
                    style={S.pagerBtn}
                    disabled={listPage === 0}
                    onClick={() => setListPage((p) => Math.max(0, p - 1))}
                  >
                    ←
                  </button>
                  <span style={S.pagerLabel}>
                    Page {listPage + 1} / {listPages}
                  </span>
                  <button
                    type="button"
                    style={S.pagerBtn}
                    disabled={listPage >= listPages - 1}
                    onClick={() => setListPage((p) => Math.min(listPages - 1, p + 1))}
                  >
                    →
                  </button>
                </div>
              </aside>

              <main style={S.editor}>
                {!current ? (
                  <div style={S.emptyEditor}>No lines match the current filters.</div>
                ) : (
                  <>
                    <div style={S.editorMeta}>
                      <span>
                        <strong>{current.character || "Unknown"}</strong>
                        {" · "}
                        {locationLabel}
                        {LOCATION_GLOSS[current.location] && (
                          <span style={S.metaRu}> ({current.location})</span>
                        )}
                      </span>
                      <span style={S.editorPos}>
                        {viewIndex + 1} / {filtered.length}
                        <span style={S.metaRu}> · row {current.i + 1}</span>
                      </span>
                    </div>

                    <div style={S.ruBlock}>
                      <div style={S.blockLabel}>Russian</div>
                      <div style={S.ruText}>{current.ru}</div>
                    </div>

                    <div style={S.enBlock}>
                      <div style={S.enHead}>
                        <div style={S.blockLabel}>English</div>
                        <div
                          style={{
                            ...S.lengthHint,
                            ...(hint.tone === "warn"
                              ? { color: "#A63A2B" }
                              : hint.tone === "ok"
                                ? { color: "#4A6B3F" }
                                : {}),
                          }}
                        >
                          {hint.label}
                        </div>
                      </div>
                      <textarea
                        ref={textareaRef}
                        style={S.textarea}
                        value={draftEn}
                        onChange={(e) => setDraftEn(e.target.value)}
                        onBlur={() => applyEdit(draftEn, draftNotes)}
                        rows={current.ru.length > 120 ? 6 : 3}
                        placeholder="Write deadpan, period English here…"
                        spellCheck
                      />
                    </div>

                    <div style={S.notesBlock}>
                      <div style={S.blockLabel}>Notes (optional)</div>
                      <input
                        style={S.notesInput}
                        value={draftNotes}
                        onChange={(e) => setDraftNotes(e.target.value)}
                        onBlur={() => applyEdit(draftEn, draftNotes)}
                        placeholder="Variant readings, glossary flags, voice timing…"
                      />
                    </div>

                    {(current.voice_file || current.sound_ref) && (
                      <div style={S.voiceMeta}>
                        {current.sound_ref && (
                          <span>
                            Sound ref: <code style={S.code}>{current.sound_ref}</code>
                          </span>
                        )}
                        {current.voice_file && (
                          <span style={S.voicePath}>{current.voice_file}</span>
                        )}
                      </div>
                    )}

                    <div style={S.navRow}>
                      <button type="button" style={S.secondaryBtn} onClick={goPrev}>
                        ← Previous
                      </button>
                      <button type="button" style={S.primaryBtn} onClick={saveAndNext}>
                        Save &amp; next open
                      </button>
                      <button type="button" style={S.secondaryBtn} onClick={goNext}>
                        Next →
                      </button>
                    </div>

                    <div style={S.shortcuts}>
                      Ctrl+S save · Ctrl+Enter save &amp; next open · N next open line ·
                      ←/→ or J/K prev/next
                    </div>
                  </>
                )}
              </main>
            </div>

            {pending === 0 && (
              <div style={S.stampWrap}>
                <div className="stamp">
                  PŘELOŽENO
                  <span className="stampSub">
                    {total.toLocaleString()} lines · certified fit for duty
                  </span>
                </div>
              </div>
            )}

            {error && <div style={S.error}>{error}</div>}
          </div>
        )}

        <div style={S.footer}>
          Human translation · style guide always visible · browser autosave · no AI
        </div>
      </div>
    </div>
  );
}

function Ledger({ label, value, warn }) {
  return (
    <div style={S.ledgerItem}>
      <div style={S.ledgerLabel}>{label}</div>
      <div style={{ ...S.ledgerValue, ...(warn ? { color: "#A63A2B" } : {}) }}>
        {value}
      </div>
    </div>
  );
}

/* ---------------------------- styling ----------------------------- */

const CSS_TEXT = `
@import url('https://fonts.googleapis.com/css2?family=Alegreya:ital,wght@0,400;0,700;1,400&family=Alegreya+SC:wght@500;700&family=Cutive+Mono&display=swap');

.dossier { box-shadow: 0 2px 0 #B5A276, 0 14px 34px rgba(43,36,24,0.28); }

.stamp {
  display: inline-block;
  transform: rotate(-7deg);
  border: 3px double #A63A2B;
  border-radius: 8px;
  color: #A63A2B;
  font-family: 'Alegreya SC', Georgia, serif;
  font-weight: 700;
  font-size: 30px;
  letter-spacing: 4px;
  padding: 12px 26px 10px;
  opacity: 0.88;
  animation: stampIn 320ms cubic-bezier(.2,1.6,.4,1) both;
  text-align: center;
}
.stamp .stampSub {
  display: block;
  font-family: 'Cutive Mono', 'Courier New', monospace;
  font-size: 12px;
  letter-spacing: 1px;
  margin-top: 4px;
}
@keyframes stampIn {
  from { transform: rotate(-7deg) scale(2.2); opacity: 0; }
  to   { transform: rotate(-7deg) scale(1);   opacity: 0.88; }
}
@media (prefers-reduced-motion: reduce) {
  .stamp { animation: none; }
}
button:focus-visible, label.stampable:focus-within, input:focus-visible, textarea:focus-visible, select:focus-visible {
  outline: 3px solid #8A6D1F; outline-offset: 2px;
}
`;

const S = {
  page: {
    minHeight: "100vh",
    background:
      "repeating-linear-gradient(0deg, #C9BC97 0, #C9BC97 2px, #C3B58E 2px, #C3B58E 46px)",
    padding: "34px 16px 60px",
    fontFamily: "'Alegreya', Georgia, serif",
    color: "#2B2418",
    display: "flex",
    justifyContent: "center",
  },
  dossier: {
    background: "#EFE6CD",
    maxWidth: 1080,
    width: "100%",
    padding: "34px 38px 26px",
    borderTop: "10px solid #6B5E3F",
  },
  header: { textAlign: "center", marginBottom: 26 },
  headerRule: { borderTop: "1px solid #9C8B66", margin: "10px 0" },
  eyebrow: {
    fontFamily: "'Cutive Mono', 'Courier New', monospace",
    fontSize: 12,
    letterSpacing: 3,
    color: "#6B5E3F",
    margin: "6px 0 2px",
  },
  title: {
    fontFamily: "'Alegreya SC', Georgia, serif",
    fontSize: 40,
    fontWeight: 700,
    margin: "2px 0 4px",
    letterSpacing: 1,
  },
  subtitle: { fontStyle: "italic", fontSize: 17, color: "#4A3F2B", marginBottom: 8 },

  intake: { textAlign: "center", padding: "18px 8px 8px" },
  intakeText: {
    fontSize: 17,
    lineHeight: 1.55,
    maxWidth: 620,
    margin: "0 auto 22px",
    textAlign: "left",
  },
  code: {
    fontFamily: "'Cutive Mono', 'Courier New', monospace",
    background: "#E2D6B4",
    padding: "1px 5px",
    fontSize: "0.92em",
  },
  uploadBtn: {
    display: "inline-block",
    background: "#2B2418",
    color: "#EFE6CD",
    fontFamily: "'Alegreya SC', Georgia, serif",
    fontSize: 18,
    letterSpacing: 1.5,
    padding: "13px 34px",
    cursor: "pointer",
  },
  uploadBtnSmall: {
    display: "inline-block",
    background: "transparent",
    color: "#2B2418",
    border: "1px solid #2B2418",
    fontFamily: "'Alegreya SC', Georgia, serif",
    fontSize: 14,
    letterSpacing: 1,
    padding: "10px 18px",
    cursor: "pointer",
  },

  ledger: {
    display: "flex",
    flexWrap: "wrap",
    gap: "14px 28px",
    borderTop: "1px solid #9C8B66",
    borderBottom: "1px solid #9C8B66",
    padding: "12px 2px",
    marginBottom: 18,
  },
  ledgerItem: { minWidth: 90 },
  ledgerLabel: {
    fontFamily: "'Cutive Mono', 'Courier New', monospace",
    fontSize: 11,
    letterSpacing: 2,
    textTransform: "uppercase",
    color: "#6B5E3F",
  },
  ledgerValue: { fontSize: 19, fontWeight: 700 },

  progressOuter: {
    position: "relative",
    height: 26,
    border: "1px solid #6B5E3F",
    background: "#E2D6B4",
    marginBottom: 18,
  },
  progressInner: {
    height: "100%",
    background: "#6B5E3F",
    transition: "width 400ms ease",
  },
  progressLabel: {
    position: "absolute",
    inset: 0,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontFamily: "'Cutive Mono', 'Courier New', monospace",
    fontSize: 13,
    color: "#2B2418",
    mixBlendMode: "multiply",
  },

  controls: { display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 14, alignItems: "center" },
  primaryBtn: {
    background: "#2B2418",
    color: "#EFE6CD",
    border: "none",
    fontFamily: "'Alegreya SC', Georgia, serif",
    fontSize: 16,
    letterSpacing: 1,
    padding: "11px 24px",
    cursor: "pointer",
  },
  secondaryBtn: {
    background: "transparent",
    color: "#2B2418",
    border: "1px solid #2B2418",
    fontFamily: "'Alegreya SC', Georgia, serif",
    fontSize: 16,
    letterSpacing: 1,
    padding: "10px 24px",
    cursor: "pointer",
  },

  filterBar: {
    display: "flex",
    flexWrap: "wrap",
    gap: 10,
    alignItems: "center",
    marginBottom: 16,
    paddingBottom: 14,
    borderBottom: "1px solid #9C8B66",
  },
  select: {
    fontFamily: "'Alegreya', Georgia, serif",
    fontSize: 15,
    padding: "8px 10px",
    border: "1px solid #6B5E3F",
    background: "#F7F0DC",
    minWidth: 180,
  },
  search: {
    flex: "1 1 200px",
    fontFamily: "'Alegreya', Georgia, serif",
    fontSize: 15,
    padding: "8px 10px",
    border: "1px solid #6B5E3F",
    background: "#F7F0DC",
  },
  checkLabel: {
    fontSize: 15,
    display: "flex",
    alignItems: "center",
    gap: 6,
    cursor: "pointer",
  },

  workspace: {
    display: "grid",
    gridTemplateColumns: "minmax(240px, 300px) 1fr",
    gap: 20,
    alignItems: "start",
  },
  sidebar: { minWidth: 0 },
  guideToggle: {
    width: "100%",
    background: "#E2D6B4",
    border: "1px solid #9C8B66",
    fontFamily: "'Alegreya SC', Georgia, serif",
    fontSize: 14,
    padding: "8px 10px",
    cursor: "pointer",
    marginBottom: 8,
  },
  guide: {
    background: "#F7F0DC",
    border: "1px solid #9C8B66",
    padding: "10px 12px",
    marginBottom: 12,
    maxHeight: 280,
    overflowY: "auto",
    fontSize: 14,
    lineHeight: 1.45,
  },
  guideSection: { marginBottom: 12 },
  guideTitle: {
    fontFamily: "'Alegreya SC', Georgia, serif",
    fontSize: 13,
    letterSpacing: 1,
    textTransform: "uppercase",
    color: "#6B5E3F",
    marginBottom: 4,
  },
  guideBody: { margin: "0 0 6px" },
  example: { marginTop: 8, paddingTop: 8, borderTop: "1px dashed #C9BC97" },
  exampleRu: { fontStyle: "italic", color: "#6B5E3F", fontSize: 13 },
  exampleEn: { fontWeight: 700, fontSize: 14, marginTop: 3 },

  listHead: {
    fontFamily: "'Cutive Mono', 'Courier New', monospace",
    fontSize: 11,
    letterSpacing: 1,
    color: "#6B5E3F",
    marginBottom: 6,
  },
  lineList: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
    maxHeight: 360,
    overflowY: "auto",
    border: "1px solid #9C8B66",
    background: "#F7F0DC",
  },
  lineItem: {
    textAlign: "left",
    border: "none",
    borderBottom: "1px solid #E2D6B4",
    background: "transparent",
    padding: "8px 10px",
    cursor: "pointer",
    fontFamily: "'Alegreya', Georgia, serif",
  },
  lineItemActive: { background: "#E2D6B4" },
  lineItemPending: { borderLeft: "3px solid #A63A2B" },
  lineItemMeta: {
    display: "block",
    fontFamily: "'Cutive Mono', 'Courier New', monospace",
    fontSize: 10,
    color: "#6B5E3F",
    marginBottom: 2,
  },
  lineItemRu: { fontSize: 13, lineHeight: 1.35 },
  listPager: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 8,
  },
  pagerBtn: {
    background: "transparent",
    border: "1px solid #6B5E3F",
    padding: "4px 12px",
    cursor: "pointer",
    fontFamily: "'Alegreya SC', Georgia, serif",
  },
  pagerLabel: {
    fontFamily: "'Cutive Mono', 'Courier New', monospace",
    fontSize: 12,
  },

  editor: {
    background: "#F7F0DC",
    border: "1px solid #9C8B66",
    padding: "16px 18px",
    minHeight: 420,
  },
  emptyEditor: { fontStyle: "italic", color: "#6B5E3F", padding: "40px 0", textAlign: "center" },
  editorMeta: {
    display: "flex",
    justifyContent: "space-between",
    gap: 12,
    flexWrap: "wrap",
    fontSize: 15,
    marginBottom: 14,
    paddingBottom: 10,
    borderBottom: "1px solid #C9BC97",
  },
  editorPos: {
    fontFamily: "'Cutive Mono', 'Courier New', monospace",
    fontSize: 13,
  },
  metaRu: { color: "#6B5E3F" },
  blockLabel: {
    fontFamily: "'Cutive Mono', 'Courier New', monospace",
    fontSize: 11,
    letterSpacing: 2,
    textTransform: "uppercase",
    color: "#6B5E3F",
    marginBottom: 6,
  },
  ruBlock: { marginBottom: 16 },
  ruText: { fontSize: 18, lineHeight: 1.5, fontStyle: "italic", color: "#4A3F2B" },
  enBlock: { marginBottom: 14 },
  enHead: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "baseline",
    gap: 10,
  },
  lengthHint: {
    fontFamily: "'Cutive Mono', 'Courier New', monospace",
    fontSize: 12,
  },
  textarea: {
    width: "100%",
    boxSizing: "border-box",
    fontFamily: "'Alegreya', Georgia, serif",
    fontSize: 18,
    lineHeight: 1.45,
    padding: "12px 14px",
    border: "1px solid #6B5E3F",
    background: "#EFE6CD",
    resize: "vertical",
    minHeight: 90,
  },
  notesBlock: { marginBottom: 12 },
  notesInput: {
    width: "100%",
    boxSizing: "border-box",
    fontFamily: "'Alegreya', Georgia, serif",
    fontSize: 15,
    padding: "8px 10px",
    border: "1px solid #9C8B66",
    background: "#EFE6CD",
  },
  voiceMeta: {
    fontFamily: "'Cutive Mono', 'Courier New', monospace",
    fontSize: 11,
    color: "#6B5E3F",
    marginBottom: 14,
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  voicePath: { wordBreak: "break-all" },
  navRow: { display: "flex", gap: 10, flexWrap: "wrap", marginTop: 8 },
  shortcuts: {
    marginTop: 12,
    fontFamily: "'Cutive Mono', 'Courier New', monospace",
    fontSize: 11,
    color: "#6B5E3F",
  },

  stampWrap: { textAlign: "center", padding: "18px 0 10px" },

  error: {
    marginTop: 14,
    padding: "10px 14px",
    border: "1px solid #A63A2B",
    color: "#A63A2B",
    fontSize: 15,
  },
  footer: {
    marginTop: 28,
    borderTop: "1px solid #9C8B66",
    paddingTop: 10,
    fontFamily: "'Cutive Mono', 'Courier New', monospace",
    fontSize: 11,
    letterSpacing: 1,
    color: "#6B5E3F",
    textAlign: "center",
  },
};