import React, { useState, useRef } from "react";
import {
  Search, FileText, ThumbsUp, ThumbsDown, Copy, ShieldCheck, ShieldAlert,
  Languages, Upload, CircleAlert, ArrowRight, Info, Clock, X, ExternalLink,
  CheckCircle2, AlertTriangle, ChevronDown, ChevronRight, FolderUp,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Mock knowledge base — illustrative only, for demo purposes.
// ---------------------------------------------------------------------------

const KB = {
  pump: {
    productLabel: "Submersible pump set — agricultural irrigation",
    standard: { code: "IS 8034 : 2018", title: "Submersible pumpsets for clear, cold, fresh water", editionNote: "Third revision, reaffirmed 2022." },
    certification: { mandatory: false, scheme: "BIS ISI Mark (voluntary)", note: "Not legally required to supply this product, but many government buyers ask for it anyway — worth requiring it from bidders." },
    specText: "Supply shall conform to IS 8034:2018 (Submersible pumpsets for clear, cold, fresh water). Pump performance shall be verified as per IS 9283. The driving motor shall conform to IS 325. Bidder to submit BIS test certificate prior to supply.",
    reason: "Matched on product type, water application, and stated power rating.",
    related: [
      { purpose: "How it's tested", code: "IS 9283", desc: "Lays out how pump performance (head, flow, efficiency) is measured." },
      { purpose: "Related component", code: "IS 325", desc: "Covers the electric motor that drives the pump." },
      { purpose: "Terms used", code: "IS 1885 (Pt 88)", desc: "Standard terminology for rotating electrical machines, if your spec needs it." },
    ],
  },
  steel_plate: {
    productLabel: "Structural steel — plates & sections",
    standard: { code: "IS 2062 : 2011", title: "Hot rolled structural steel", editionNote: "Current edition." },
    certification: { mandatory: true, scheme: "BIS Licensing", note: "Mandatory for specific grades. Confirm the exact grade in your BOQ before finalising, then check the supplier's BIS licence covers that grade." },
    specText: "Structural steel sections/plates shall conform to IS 2062:2011, Grade E250 (or as specified in the BOQ). Design and construction shall follow IS 800:2007. Material test certificates as per IS 1608 to be submitted for each batch.",
    reason: "Matched structural framing use once the steel form was confirmed as plates/sections.",
    related: [
      { purpose: "How it's tested", code: "IS 1608", desc: "Tensile testing method for the steel batch." },
      { purpose: "Design code to follow", code: "IS 800:2007", desc: "Referenced whenever this steel is used in a structural design." },
      { purpose: "Related component", code: "IS 1852", desc: "Rolling and cutting tolerances for the sections you receive." },
    ],
  },
  steel_rebar: {
    productLabel: "Structural steel — reinforcement bars",
    standard: { code: "IS 1786 : 2008", title: "High strength deformed bars for concrete reinforcement", editionNote: "Amended 2013 — make sure quotes reference the amended version." },
    certification: { mandatory: true, scheme: "BIS Compulsory Licensing", note: "Mandatory. Do not accept supply without checking the supplier's BIS licence number is valid for this product." },
    specText: "Reinforcement steel shall conform to IS 1786:2008 (as amended 2013), Fe 500 / Fe 500D as specified in the BOQ. Design shall follow IS 456:2000. Bidder's BIS licence number to be verified and recorded before award.",
    reason: "Matched reinforcement/rebar use once the steel form was confirmed as concrete reinforcement.",
    related: [
      { purpose: "How it's tested", code: "IS 1608", desc: "Tensile testing method for the bars." },
      { purpose: "Design code to follow", code: "IS 456:2000", desc: "Governs how reinforced concrete using these bars is designed." },
    ],
  },
  steel_sheet: {
    productLabel: "Structural steel — roofing/cladding sheet",
    standard: { code: "IS 277 : 2018", title: "Galvanized steel sheets, plain & corrugated", editionNote: "Current edition." },
    certification: { mandatory: false, scheme: "BIS ISI Mark (voluntary)", note: "Not mandatory, but recommended as a supply condition for quality assurance." },
    specText: "Roofing/cladding sheets shall conform to IS 277:2018, zinc coating grade as specified in the BOQ. Fastening shall follow IS 730 recommendations.",
    reason: "Matched sheet/cladding use once the steel form was confirmed as roofing material.",
    related: [
      { purpose: "How it's tested", code: "IS 6745", desc: "Checks the mass of zinc coating applied." },
      { purpose: "Installation guidance", code: "IS 730", desc: "Recommended fasteners for this type of sheeting." },
    ],
  },
  cable: {
    productLabel: "PVC insulated electrical cable — 1.1kV",
    standard: { code: "IS 694 : 2010", title: "PVC insulated cables up to 1100V", editionNote: "Amended 2018 — cite the amended version in your tender." },
    certification: { mandatory: true, scheme: "BIS ISI Mark", note: "Mandatory under a Quality Control Order for this product category. Suppliers without a valid BIS licence cannot legally supply this cable." },
    specText: "Cables shall conform to IS 694:2010 (as amended 2018), PVC insulated, rated 1100V. BIS ISI mark is mandatory under the applicable Quality Control Order — bidder to furnish licence details. Current ratings shall be derived as per IS 3961.",
    reason: "Voltage grade (1.1kV) and insulation type (PVC) matched this standard's stated scope exactly.",
    related: [
      { purpose: "Material spec", code: "IS 5831", desc: "Covers the PVC insulation/sheath compound itself." },
      { purpose: "How it's tested", code: "IS 10810", desc: "Series of test methods used to verify the cable." },
      { purpose: "Sizing guidance", code: "IS 3961", desc: "Used to work out safe current ratings for your installation." },
    ],
  },
  cement: {
    productLabel: "Ordinary Portland Cement — general construction",
    standard: { code: "IS 269 : 2013", title: "Ordinary Portland Cement, Specification", editionNote: "Current edition." },
    certification: { mandatory: true, scheme: "BIS ISI Mark", note: "Mandatory. Cement cannot be legally sold in India without a valid BIS licence for the grade supplied." },
    specText: "Cement supplied shall conform to IS 269:2013 (OPC 33 grade), or IS 8112 / IS 12269 for 43/53 grade as specified in the BOQ. BIS ISI mark is mandatory. Sampling and testing as per IS 4031 (series).",
    reason: "Matched on 'cement' and general construction application.",
    related: [
      { purpose: "How it's tested", code: "IS 4031 (series)", desc: "Methods of physical testing for cement (setting time, strength, fineness)." },
      { purpose: "Related grade", code: "IS 12269", desc: "Covers 53-grade OPC if higher strength is needed." },
      { purpose: "Test material", code: "IS 650", desc: "Standard sand used when testing cement strength." },
    ],
  },
  pipe: {
    productLabel: "Galvanized steel pipe — water supply",
    standard: { code: "IS 1239 (Part 1) : 2004", title: "Mild steel tubes, tubulars and other wrought steel fittings", editionNote: "Amended 2004 series — check latest amendment slip before citing." },
    certification: { mandatory: true, scheme: "BIS ISI Mark", note: "Mandatory under QCO for GI pipes used in water supply. Verify supplier's BIS licence before award." },
    specText: "Pipes shall conform to IS 1239 (Part 1):2004, medium class, hot-dip galvanized. Fittings shall conform to IS 1239 (Part 2). Zinc coating to be verified as per IS 4736.",
    reason: "Matched on pipe/tube keywords and water-supply application.",
    related: [
      { purpose: "Fittings", code: "IS 1239 (Part 2) : 2011", desc: "Covers the fittings (elbows, tees, sockets) used with this pipe." },
      { purpose: "How it's tested", code: "IS 4736", desc: "Checks the zinc coating applied for corrosion protection." },
      { purpose: "Related product", code: "IS 3589", desc: "Covers larger-diameter steel pipes if this size range doesn't fit." },
    ],
  },
};

// `archive` = verified exact document page on the Internet Archive's public
// mirror of Indian Standards (Public.Resource.Org / law.resource.org corpus).
// Where no specific edition was verified for this POC, `search` is used
// instead — a scoped search on the same archive, not a guess at a URL.
function archiveLink(item) { return { url: `https://archive.org/details/${item}`, exact: true }; }
function searchLink(code) { return { url: `https://archive.org/search?query=${encodeURIComponent(code + " bureau of indian standards")}`, exact: false }; }

const STANDARD_INFO = {
  "IS 8034 : 2018": { scope: "Covers design, materials, and performance requirements for submersible pumpsets used to lift clear, cold, fresh water for domestic, agricultural, and industrial use.", params: [["Power range", "0.75 – 20 HP"], ["Discharge", "As per rated head, tested per IS 9283"], ["Test basis", "IS 9283"]], link: archiveLink("gov.in.is.8034.2018") },
  "IS 9283": { scope: "Specifies the test methods used to verify a pump's head, discharge, and efficiency against its rated performance.", params: [["Applies to", "Submersible & other rotodynamic pumps"]], link: searchLink("IS 9283") },
  "IS 325": { scope: "Specification for three-phase induction motors, including the type commonly used to drive submersible pumps.", params: [["Type", "Three-phase induction motor"]], link: searchLink("IS 325") },
  "IS 1885 (Pt 88)": { scope: "Defines standard terminology used across rotating electrical machinery standards, for consistent wording in specifications.", params: [], link: searchLink("IS 1885 Part 88") },
  "IS 2062 : 2011": { scope: "Specification for hot-rolled medium and high-tensile structural steel used in plates, sections, and beams for general construction.", params: [["Grades", "E165, E250, E300, E350, E410, E450"], ["Typical plate thickness", "5 – 40 mm"], ["Yield strength (E250)", "250 MPa min"]], link: archiveLink("gov.in.is.2062.2011") },
  "IS 1608": { scope: "Method of tensile testing for steel products, used to verify batches meet the strength grade specified.", params: [["Test type", "Tensile test"]], link: archiveLink("gov.in.is.1608.2005") },
  "IS 800:2007": { scope: "General design code for the use of structural steel in construction — governs how the material is designed into a structure, not the material itself.", params: [], link: archiveLink("gov.in.is.800.2007") },
  "IS 1852": { scope: "Specifies rolling and cutting dimensional tolerances for structural steel sections and plates.", params: [], link: searchLink("IS 1852") },
  "IS 1786 : 2008": { scope: "Specification for high-strength deformed steel bars used as reinforcement inside concrete.", params: [["Grades", "Fe 415, Fe 500, Fe 500D, Fe 550"], ["Diameter range", "8 – 40 mm"]], link: archiveLink("gov.in.is.1786.2008") },
  "IS 456:2000": { scope: "General code of practice for plain and reinforced concrete design and construction.", params: [], link: archiveLink("gov.in.is.456.2000") },
  "IS 277 : 2018": { scope: "Specification for galvanized (zinc-coated) steel sheets, plain and corrugated, used for roofing and cladding.", params: [["Zinc coating classes", "Z100 – Z600"], ["Base metal thickness", "0.40 – 3.15 mm"]], link: archiveLink("gov.in.is.277.2018") },
  "IS 6745": { scope: "Method of test for determining the mass of zinc coating on galvanized steel sheet.", params: [], link: searchLink("IS 6745") },
  "IS 730": { scope: "Recommends the type and spacing of fasteners for corrugated steel sheeting.", params: [], link: searchLink("IS 730") },
  "IS 694 : 2010": { scope: "Specification for PVC insulated cables for working voltages up to and including 1100V, covering construction and testing.", params: [["Voltage grade", "Up to 1100V"], ["Conductor", "Copper or aluminium"], ["Insulation", "PVC, Type A"]], link: archiveLink("gov.in.is.694.2010") },
  "IS 5831": { scope: "Specifies the PVC compound used for cable insulation and sheathing, independent of the finished cable standard.", params: [], link: searchLink("IS 5831") },
  "IS 10810": { scope: "A series of test methods for cables — covering insulation resistance, voltage withstand, and more.", params: [], link: searchLink("IS 10810") },
  "IS 3961": { scope: "Gives recommended current-carrying capacity (ratings) for cables under different installation conditions.", params: [], link: searchLink("IS 3961") },
  "IS 269 : 2013": { scope: "Specification for 33-grade Ordinary Portland Cement, covering composition, strength, and setting-time requirements.", params: [["Grade", "OPC 33 (see IS 8112 / IS 12269 for 43/53)"], ["Initial setting time", "≥ 30 minutes"], ["28-day compressive strength", "≥ 33 MPa"]], link: archiveLink("gov.in.is.269.2013") },
  "IS 4031 (series)": { scope: "Methods of physical testing for cement — setting time, fineness, soundness, and compressive strength.", params: [], link: searchLink("IS 4031") },
  "IS 12269": { scope: "Specification for 53-grade Ordinary Portland Cement, for applications needing higher early strength.", params: [], link: searchLink("IS 12269") },
  "IS 650": { scope: "Specifies the standard sand used as a reference material when testing cement strength.", params: [], link: searchLink("IS 650") },
  "IS 1239 (Part 1) : 2004": { scope: "Specification for mild steel tubes used in water, gas, and steam lines at low pressure.", params: [["Nominal bore", "6 mm – 150 mm"], ["Classes", "Light, Medium, Heavy"], ["Coating", "Hot-dip galvanized"]], link: archiveLink("gov.in.is.1239.1.2004") },
  "IS 1239 (Part 2) : 2011": { scope: "Covers the wrought steel pipe fittings (elbows, tees, sockets) used with Part 1 tubes.", params: [], link: archiveLink("gov.in.is.1239.2.2011") },
  "IS 4736": { scope: "Method of test for the zinc coating applied to galvanized pipes and fittings.", params: [], link: searchLink("IS 4736") },
  "IS 3589": { scope: "Specification for larger-diameter electrically welded steel pipes, used where Part 1 sizes aren't sufficient.", params: [], link: searchLink("IS 3589") },
};

const SAMPLE_QUERIES = [
  { id: "pump", label: "5 HP submersible pump, agricultural use" },
  { id: "steel", label: "Steel for a warehouse structure" },
  { id: "cable", label: "PVC insulated electrical cable, 1.1kV" },
];

function matchQuery(text) {
  const t = text.toLowerCase();
  if (t.includes("steel")) {
    if (t.match(/rebar|reinforc/)) return { type: "direct", id: "steel_rebar" };
    if (t.match(/sheet|roof|clad/)) return { type: "direct", id: "steel_sheet" };
    if (t.match(/plate|section|beam|structur|frame|warehouse|column/)) return { type: "direct", id: "steel_plate" };
    return { type: "ambiguous" };
  }
  if (t.match(/pump/)) return { type: "direct", id: "pump" };
  if (t.match(/cable|wire/)) return { type: "direct", id: "cable" };
  if (t.match(/cement|\bopc\b|\bppc\b/)) return { type: "direct", id: "cement" };
  if (t.match(/pipe|tube/)) return { type: "direct", id: "pipe" };
  return { type: "none" };
}

const STEEL_CLARIFY = {
  question: "What is the steel for?",
  helper: "This changes which standard applies — picking the wrong one is a common tender error.",
  options: [
    { id: "steel_plate", label: "Structural framing (plates, beams, sections)" },
    { id: "steel_rebar", label: "Reinforcement bars inside concrete" },
    { id: "steel_sheet", label: "Roofing or cladding sheets" },
  ],
};

// ---------------------------------------------------------------------------

const ink = "#1c2438";
const paper = "#f1efe6";
const paperDeep = "#e7e3d4";
const brass = "#a9722f";
const seal = "#8a3324";
const line = "#c9c3ab";
const good = "#3f6b4e";
const sans = "Helvetica, Arial, sans-serif";
const serif = "Georgia, 'Iowan Old Style', serif";

function hashStr(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h;
}

// -- Standard detail panel ---------------------------------------------------

function StandardModal({ code, onClose }) {
  const info = STANDARD_INFO[code];
  if (!info) return null;
  return (
    <div
      onClick={onClose}
      style={{ position: "fixed", inset: 0, background: "rgba(28,36,56,0.45)", zIndex: 50, display: "flex", alignItems: "flex-end", justifyContent: "center" }}
      className="md:items-center"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ background: paper, border: `1px solid ${line}`, borderRadius: 8, maxWidth: 480, width: "92%", maxHeight: "80vh", overflowY: "auto" }}
        className="p-6 mb-4 md:mb-0"
      >
        <div className="flex items-start justify-between mb-3">
          <div style={{ fontFamily: serif, fontSize: 20, color: ink }}>{code}</div>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "#8b8570" }}>
            <X size={18} />
          </button>
        </div>
        <p style={{ fontSize: 14, color: "#42402f", marginBottom: 14, lineHeight: 1.5 }}>{info.scope}</p>
        {info.params.length > 0 && (
          <div style={{ border: `1px solid ${line}`, borderRadius: 6, overflow: "hidden", marginBottom: 14 }}>
            {info.params.map(([k, v], i) => (
              <div key={k} className="flex" style={{ borderTop: i === 0 ? "none" : `1px solid ${line}` }}>
                <div style={{ width: "42%", fontSize: 12.5, color: "#8b8570", fontFamily: sans, padding: "8px 12px", background: "rgba(0,0,0,0.02)" }}>{k}</div>
                <div style={{ fontSize: 13, color: ink, padding: "8px 12px" }}>{v}</div>
              </div>
            ))}
          </div>
        )}
        <a
          href={info.link.url}
          target="_blank"
          rel="noreferrer"
          style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13, color: brass, fontFamily: sans, textDecoration: "none" }}
        >
          {info.link.exact ? "Open the document" : "Search for this document"} <ExternalLink size={13} />
        </a>
        <p style={{ fontSize: 11, color: "#a5a08c", marginTop: 10, fontFamily: sans }}>
          {info.link.exact
            ? "Opens the actual standard on the Internet Archive's public mirror of Indian Standards. Scope and parameters above are a summary, not the full text."
            : "This exact edition wasn't verified for this POC, so this searches the Internet Archive's Indian Standards mirror for it instead of guessing a link."}
        </p>
      </div>
    </div>
  );
}

function CodeLink({ code, onOpen }) {
  const hasInfo = !!STANDARD_INFO[code];
  return (
    <button
      onClick={() => hasInfo && onOpen(code)}
      style={{
        fontFamily: serif, fontSize: "inherit", color: hasInfo ? brass : "inherit", background: "none",
        border: "none", padding: 0, cursor: hasInfo ? "pointer" : "default", textDecoration: hasInfo ? "underline" : "none",
        textDecorationColor: "rgba(169,114,47,0.4)",
      }}
    >
      {code}
    </button>
  );
}

// -- Single-query result view ------------------------------------------------

function CertificationBox({ certification }) {
  const mandatory = certification.mandatory;
  return (
    <div style={{ border: `1px solid ${mandatory ? seal : good}`, background: mandatory ? "#f3e6e2" : "#e9f1eb", borderRadius: 6 }} className="p-4 flex gap-3">
      {mandatory ? <ShieldAlert size={20} style={{ color: seal, flexShrink: 0, marginTop: 1 }} /> : <ShieldCheck size={20} style={{ color: good, flexShrink: 0, marginTop: 1 }} />}
      <div>
        <div style={{ fontSize: 14.5, color: mandatory ? seal : good, fontFamily: sans, fontWeight: 600 }}>
          {mandatory ? "Certification is mandatory" : "Certification is not mandatory"}
        </div>
        <div style={{ fontSize: 13, color: "#4a4636", marginTop: 2, fontFamily: sans }}>{certification.scheme}</div>
        <p style={{ fontSize: 13.5, color: "#5c5843", marginTop: 6 }}>{certification.note}</p>
      </div>
    </div>
  );
}

function SpecBlock({ text }) {
  const [copied, setCopied] = useState(false);
  return (
    <div style={{ border: `1px solid ${line}`, borderRadius: 6, background: "rgba(255,255,255,0.6)" }}>
      <div className="flex items-center justify-between px-4 pt-3">
        <span style={{ fontSize: 11.5, color: "#8b8570", fontFamily: sans, letterSpacing: 0.3 }}>Draft wording for your tender</span>
        <button
          onClick={() => { navigator.clipboard?.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
          style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12.5, color: brass, background: "none", border: "none", cursor: "pointer", fontFamily: sans }}
        >
          <Copy size={13} /> {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <p style={{ fontSize: 14.5, color: ink, padding: "10px 16px 16px", lineHeight: 1.55 }}>{text}</p>
    </div>
  );
}

function ResultView({ data, onOpenStandard }) {
  const [feedback, setFeedback] = useState(null);
  return (
    <div>
      <h2 style={{ fontSize: 21, color: ink, fontWeight: 400, marginBottom: 2 }}>{data.productLabel}</h2>
      <p style={{ fontSize: 13.5, color: "#6b6650", fontFamily: sans, marginBottom: 18 }}>{data.reason}</p>

      <div className="flex items-start justify-between flex-wrap gap-3 mb-5 pb-5" style={{ borderBottom: `1px solid ${line}` }}>
        <div>
          <div style={{ fontSize: 11.5, color: "#8b8570", fontFamily: sans, marginBottom: 3 }}>STANDARD TO CITE</div>
          <div style={{ fontSize: 19 }}><CodeLink code={data.standard.code} onOpen={onOpenStandard} /></div>
          <div style={{ fontSize: 14, color: "#42402f", marginTop: 2 }}>{data.standard.title}</div>
        </div>
        <div className="flex items-start gap-1.5" style={{ maxWidth: 220 }}>
          <Clock size={14} style={{ color: brass, marginTop: 2, flexShrink: 0 }} />
          <span style={{ fontSize: 12.5, color: "#6b6650", fontFamily: sans }}>{data.standard.editionNote}</span>
        </div>
      </div>

      <div className="mb-5"><CertificationBox certification={data.certification} /></div>
      <div className="mb-6"><SpecBlock text={data.specText} /></div>

      <div className="mb-6">
        <div style={{ fontSize: 11.5, color: "#8b8570", fontFamily: sans, marginBottom: 10 }}>ALSO WORTH REFERENCING — tap a code to read what it covers</div>
        <div className="flex flex-col gap-3">
          {data.related.map((r) => (
            <div key={r.code} className="flex items-start gap-3">
              <div style={{ fontSize: 11, color: brass, border: `1px solid ${brass}`, borderRadius: 4, padding: "2px 6px", fontFamily: sans, flexShrink: 0, marginTop: 1, whiteSpace: "nowrap" }}>
                {r.purpose}
              </div>
              <div style={{ fontSize: 14.5 }}>
                <CodeLink code={r.code} onOpen={onOpenStandard} />
                <span style={{ fontSize: 13.5, color: "#6b6650" }}> — {r.desc}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3 pt-2" style={{ borderTop: `1px solid ${line}` }}>
        <span style={{ fontSize: 12.5, color: "#8b8570", fontFamily: sans, marginTop: 10 }}>Does this look right?</span>
        <div className="flex gap-2 mt-2">
          <button onClick={() => setFeedback("up")} style={{ border: `1px solid ${feedback === "up" ? good : line}`, background: feedback === "up" ? "#e7efe9" : "transparent", color: feedback === "up" ? good : "#6b6650", borderRadius: 4, padding: "4px 7px", cursor: "pointer" }}>
            <ThumbsUp size={13} />
          </button>
          <button onClick={() => setFeedback("down")} style={{ border: `1px solid ${feedback === "down" ? seal : line}`, background: feedback === "down" ? "#f3e6e2" : "transparent", color: feedback === "down" ? seal : "#6b6650", borderRadius: 4, padding: "4px 7px", cursor: "pointer" }}>
            <ThumbsDown size={13} />
          </button>
        </div>
        {feedback && <span style={{ fontSize: 12, color: "#8b8570", fontFamily: sans, marginTop: 10 }}>Thanks — noted.</span>}
      </div>
    </div>
  );
}

// -- Bulk mode ----------------------------------------------------------------

const KB_IDS = Object.keys(KB);

function mockAnalyzeFile(file) {
  const h = hashStr(file.name + file.size);
  const id = KB_IDS[h % KB_IDS.length];
  const entry = KB[id];
  const pass = h % 10 < 7; // ~70% pass rate, deterministic per file
  return {
    fileName: file.name,
    productLabel: entry.productLabel,
    standardCode: entry.standard.code,
    certification: entry.certification,
    status: pass ? "pass" : "review",
    statusNote: pass
      ? "Meets the mandatory quality/certification requirement for this product."
      : entry.certification.mandatory
      ? "Mandatory certification not confirmed in this document — needs review before award."
      : "Specification incomplete — grade/class not clearly stated.",
  };
}

function BulkPanel({ onBack }) {
  const [files, setFiles] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const [stage, setStage] = useState("collect"); // collect | loading | done
  const [results, setResults] = useState([]);
  const [onlyPass, setOnlyPass] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const inputRef = useRef(null);

  const addFiles = (list) => {
    const incoming = Array.from(list);
    setFiles((prev) => {
      const combined = [...prev, ...incoming];
      return combined.slice(0, 50);
    });
  };

  const removeFile = (idx) => setFiles((prev) => prev.filter((_, i) => i !== idx));

  const analyze = () => {
    setStage("loading");
    setTimeout(() => {
      setResults(files.map(mockAnalyzeFile));
      setStage("done");
    }, 1100);
  };

  const reset = () => { setFiles([]); setResults([]); setStage("collect"); };

  if (stage === "done") {
    const passing = results.filter((r) => r.status === "pass");
    const minStandards = Array.from(new Set(passing.map((r) => r.standardCode)));
    const visible = onlyPass ? passing : results;
    return (
      <div>
        <button onClick={onBack} style={{ fontSize: 12.5, color: "#8b8570", background: "none", border: "none", cursor: "pointer", marginBottom: 16, fontFamily: sans }}>← Back</button>

        <div style={{ border: `1px solid ${line}`, borderRadius: 6, background: "rgba(255,255,255,0.5)" }} className="p-5 mb-6">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle2 size={17} style={{ color: good }} />
            <span style={{ fontSize: 15, color: ink }}>
              {passing.length} of {results.length} tenders meet mandatory quality requirements
            </span>
          </div>
          <p style={{ fontSize: 13, color: "#6b6650", fontFamily: sans }}>
            Minimum set of standards needed to cover every compliant item:{" "}
            {minStandards.map((c, i) => (
              <span key={c}>
                <span style={{ fontFamily: serif, color: brass }}>{c}</span>
                {i < minStandards.length - 1 ? ", " : ""}
              </span>
            ))}
          </p>
        </div>

        <label className="flex items-center gap-2 mb-4" style={{ fontSize: 13, color: "#6b6650", fontFamily: sans }}>
          <input type="checkbox" checked={onlyPass} onChange={(e) => setOnlyPass(e.target.checked)} />
          Show only items that pass
        </label>

        <div style={{ borderTop: `1px solid ${ink}` }}>
          {visible.map((r, i) => {
            const pass = r.status === "pass";
            return (
              <div key={r.fileName + i} style={{ borderBottom: `1px solid ${line}` }} className="py-3">
                <button
                  onClick={() => setExpanded(expanded === i ? null : i)}
                  className="w-full flex items-center justify-between gap-3"
                  style={{ background: "none", border: "none", cursor: "pointer", padding: 0, textAlign: "left" }}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    {pass ? <CheckCircle2 size={15} style={{ color: good, flexShrink: 0 }} /> : <AlertTriangle size={15} style={{ color: seal, flexShrink: 0 }} />}
                    <span style={{ fontSize: 13.5, color: ink, fontFamily: sans, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.fileName}</span>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <span style={{ fontSize: 12.5, color: "#6b6650", fontFamily: sans }}>{r.productLabel}</span>
                    {expanded === i ? <ChevronDown size={14} style={{ color: "#8b8570" }} /> : <ChevronRight size={14} style={{ color: "#8b8570" }} />}
                  </div>
                </button>
                {expanded === i && (
                  <div className="mt-3 pl-6 flex flex-col gap-2">
                    <div style={{ fontSize: 13.5 }}>
                      Standard: <span style={{ fontFamily: serif, color: brass }}>{r.standardCode}</span>
                    </div>
                    <div style={{ fontSize: 13, color: pass ? good : seal, fontFamily: sans }}>{r.statusNote}</div>
                    <div style={{ fontSize: 12.5, color: "#6b6650", fontFamily: sans }}>
                      Certification: {r.certification.scheme} {r.certification.mandatory ? "(mandatory)" : "(voluntary)"}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  if (stage === "loading") {
    return (
      <div className="flex flex-col gap-3">
        <p style={{ fontSize: 15, color: ink, fontFamily: sans }}>Checking {files.length} documents against Indian Standards…</p>
      </div>
    );
  }

  return (
    <div>
      <button onClick={onBack} style={{ fontSize: 12.5, color: "#8b8570", background: "none", border: "none", cursor: "pointer", marginBottom: 16, fontFamily: sans }}>← Back</button>
      <h1 style={{ fontSize: 22, color: ink, marginBottom: 6, fontWeight: 400 }}>Check multiple tenders at once</h1>
      <p style={{ fontSize: 14, color: "#6b6650", marginBottom: 18, fontFamily: sans }}>
        Upload up to 50 tender or product-specification files. Each is checked separately, and you'll see which ones meet mandatory quality requirements.
      </p>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); addFiles(e.dataTransfer.files); }}
        style={{
          border: `1.5px dashed ${dragOver ? brass : line}`,
          borderRadius: 6,
          background: dragOver ? "rgba(169,114,47,0.06)" : "rgba(255,255,255,0.4)",
        }}
        className="flex flex-col items-center justify-center gap-2 py-12 mb-4"
      >
        <FolderUp size={22} style={{ color: brass }} />
        <span style={{ fontSize: 13.5, color: "#6b6650", fontFamily: sans }}>Drag and drop files here, or</span>
        <button
          onClick={() => inputRef.current?.click()}
          style={{ fontSize: 13, color: seal, background: "none", border: "none", textDecoration: "underline", cursor: "pointer", fontFamily: sans }}
        >
          browse your computer
        </button>
        <span style={{ fontSize: 11.5, color: "#a5a08c", fontFamily: sans }}>Up to 50 files · PDF, DOCX</span>
        <input ref={inputRef} type="file" multiple hidden onChange={(e) => addFiles(e.target.files)} />
      </div>

      {files.length > 0 && (
        <div style={{ border: `1px solid ${line}`, borderRadius: 6, background: "rgba(255,255,255,0.5)" }} className="mb-4">
          <div className="flex items-center justify-between px-4 py-2.5" style={{ borderBottom: `1px solid ${line}` }}>
            <span style={{ fontSize: 12.5, color: "#6b6650", fontFamily: sans }}>{files.length} file{files.length > 1 ? "s" : ""} added {files.length >= 50 ? "(limit reached)" : ""}</span>
            <button onClick={() => setFiles([])} style={{ fontSize: 12, color: seal, background: "none", border: "none", cursor: "pointer", fontFamily: sans }}>Clear all</button>
          </div>
          <div style={{ maxHeight: 220, overflowY: "auto" }}>
            {files.map((f, i) => (
              <div key={f.name + i} className="flex items-center justify-between px-4 py-2" style={{ borderTop: i === 0 ? "none" : `1px solid ${paperDeep}` }}>
                <span style={{ fontSize: 13, color: ink, fontFamily: sans, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.name}</span>
                <button onClick={() => removeFile(i)} style={{ background: "none", border: "none", cursor: "pointer", color: "#8b8570", flexShrink: 0 }}>
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <button
        disabled={files.length === 0}
        onClick={analyze}
        style={{ display: "flex", alignItems: "center", gap: 8, background: files.length ? ink : "#b8b39d", color: paper, border: "none", borderRadius: 4, padding: "10px 18px", fontSize: 14, cursor: files.length ? "pointer" : "not-allowed", fontFamily: sans }}
      >
        <Search size={15} /> Check {files.length || ""} tender{files.length === 1 ? "" : "s"}
      </button>
    </div>
  );
}

// -- App ----------------------------------------------------------------------

export default function App() {
  const [query, setQuery] = useState("");
  const [stage, setStage] = useState("idle"); // idle | loading | clarify | done | none | bulk
  const [dataset, setDataset] = useState(null);
  const [modalCode, setModalCode] = useState(null);

  const runQuery = (text) => {
    setQuery(text);
    setStage("loading");
    setTimeout(() => {
      const m = matchQuery(text);
      if (m.type === "direct") { setDataset(KB[m.id]); setStage("done"); }
      else if (m.type === "ambiguous") { setDataset({ clarify: STEEL_CLARIFY }); setStage("clarify"); }
      else { setStage("none"); }
    }, 800);
  };

  const reset = () => { setStage("idle"); setQuery(""); setDataset(null); };

  if (stage === "bulk") {
    return (
      <div style={{ background: paper, minHeight: "100%", fontFamily: serif }} className="w-full">
        <style>{`* { box-sizing: border-box; } input, textarea, button { font-family: inherit; } ::placeholder { color: #a5a08c; }`}</style>
        <div style={{ borderBottom: `1px solid ${line}` }} className="px-6 md:px-10 py-4 flex items-center gap-3">
          <FileText size={20} style={{ color: seal }} />
          <div style={{ fontSize: 16, color: ink }}>Standard Setu — bulk check</div>
        </div>
        <div className="px-6 md:px-10 py-8 max-w-3xl mx-auto">
          <BulkPanel onBack={() => setStage("idle")} />
        </div>
      </div>
    );
  }

  return (
    <div style={{ background: paper, minHeight: "100%", fontFamily: serif }} className="w-full">
      <style>{`* { box-sizing: border-box; } input, textarea, button { font-family: inherit; } ::placeholder { color: #a5a08c; }`}</style>
      {modalCode && <StandardModal code={modalCode} onClose={() => setModalCode(null)} />}

      <div style={{ borderBottom: `1px solid ${line}` }} className="px-6 md:px-10 py-4 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <FileText size={20} style={{ color: seal }} />
          <div>
            <div style={{ fontSize: 16, color: ink }}>Standard Setu</div>
            <div style={{ fontSize: 11.5, color: "#8b8570", fontFamily: sans }}>Know what to write in your tender, and what you're required to check</div>
          </div>
        </div>
        <div className="flex items-center gap-1.5" style={{ fontSize: 12.5, color: "#6b6650", fontFamily: sans }}>
          <Languages size={14} />
          English / हिंदी
        </div>
      </div>

      <div className="px-6 md:px-10 py-8 max-w-3xl mx-auto">
        {stage === "idle" && (
          <div>
            <h1 style={{ fontSize: 25, color: ink, marginBottom: 6, fontWeight: 400 }}>What are you procuring?</h1>
            <p style={{ fontSize: 14, color: "#6b6650", marginBottom: 20, fontFamily: sans }}>
              Describe it the way you normally would — material, capacity, application. You'll get the standard to cite, the certification you need to check for, and wording you can paste into your specification.
            </p>

            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && query.trim()) { e.preventDefault(); runQuery(query); } }}
              placeholder="e.g. GI pipe for water supply, cement for a bridge, PVC cable rated 1.1kV..."
              style={{ width: "100%", minHeight: 90, border: `1px solid ${line}`, borderRadius: 4, background: "rgba(255,255,255,0.5)", padding: "12px 14px", fontSize: 15, color: ink, resize: "vertical" }}
            />

            <div className="flex items-center justify-between mt-4 flex-wrap gap-3">
              <div className="flex items-center gap-2 flex-wrap">
                <span style={{ fontSize: 12, color: "#8b8570", fontFamily: sans }}>Try:</span>
                {SAMPLE_QUERIES.map((s) => (
                  <button key={s.id} onClick={() => runQuery(s.label)} style={{ fontSize: 12.5, color: "#6b6650", border: `1px solid ${line}`, borderRadius: 20, padding: "4px 12px", background: "rgba(255,255,255,0.4)", cursor: "pointer", fontFamily: sans }}>
                    {s.label}
                  </button>
                ))}
              </div>
              <button
                disabled={!query.trim()}
                onClick={() => runQuery(query)}
                style={{ display: "flex", alignItems: "center", gap: 8, background: query.trim() ? ink : "#b8b39d", color: paper, border: "none", borderRadius: 4, padding: "10px 18px", fontSize: 14, cursor: query.trim() ? "pointer" : "not-allowed", fontFamily: sans }}
              >
                <Search size={15} /> Find the standard
              </button>
            </div>

            <div className="mt-6 pt-5 flex items-start gap-2" style={{ borderTop: `1px solid ${line}` }}>
              <Upload size={15} style={{ color: brass, marginTop: 1 }} />
              <p style={{ fontSize: 13, color: "#6b6650", fontFamily: sans }}>
                Have full tender documents instead?{" "}
                <button onClick={() => setStage("bulk")} style={{ color: seal, background: "none", border: "none", textDecoration: "underline", cursor: "pointer", fontFamily: sans }}>
                  Check up to 50 at once
                </button>
              </p>
            </div>
          </div>
        )}

        {stage === "loading" && (
          <div className="flex flex-col gap-4">
            <button onClick={reset} style={{ fontSize: 12.5, color: "#8b8570", background: "none", border: "none", cursor: "pointer", alignSelf: "flex-start", fontFamily: sans }}>← Back</button>
            <p style={{ fontSize: 15.5, color: ink, fontStyle: "italic" }}>{query}</p>
            <div className="flex items-center gap-2" style={{ color: "#8b8570", fontSize: 14, fontFamily: sans }}>
              <Search size={15} /> Checking Indian Standards for this…
            </div>
          </div>
        )}

        {stage === "none" && (
          <div>
            <button onClick={reset} style={{ fontSize: 12.5, color: "#8b8570", background: "none", border: "none", cursor: "pointer", marginBottom: 16, fontFamily: sans }}>← Back</button>
            <p style={{ fontSize: 15.5, color: ink, fontStyle: "italic", marginBottom: 16 }}>{query}</p>
            <div style={{ border: `1px solid ${line}`, borderRadius: 6, background: "rgba(255,255,255,0.5)" }} className="p-5">
              <div className="flex items-start gap-2 mb-2">
                <CircleAlert size={17} style={{ color: brass, marginTop: 1 }} />
                <p style={{ fontSize: 14.5, color: ink }}>Couldn't confidently match this to a standard yet.</p>
              </div>
              <p style={{ fontSize: 13, color: "#6b6650", fontFamily: sans, marginLeft: 25 }}>
                This POC only covers a handful of product types. Try adding the material, product type, or application — e.g. "GI pipe", "cement", "cable", "pump", or "steel".
              </p>
            </div>
          </div>
        )}

        {stage === "clarify" && (
          <div>
            <button onClick={reset} style={{ fontSize: 12.5, color: "#8b8570", background: "none", border: "none", cursor: "pointer", marginBottom: 16, fontFamily: sans }}>← Back</button>
            <p style={{ fontSize: 15.5, color: ink, fontStyle: "italic", marginBottom: 20 }}>{query}</p>
            <div style={{ border: `1px solid ${brass}`, borderRadius: 6, background: "#f6ecda" }} className="p-5">
              <div className="flex items-start gap-2 mb-2">
                <CircleAlert size={17} style={{ color: brass, marginTop: 1 }} />
                <p style={{ fontSize: 15, color: ink }}>{dataset.clarify.question}</p>
              </div>
              <p style={{ fontSize: 12.5, color: "#8b7a55", marginBottom: 14, fontFamily: sans, marginLeft: 25 }}>{dataset.clarify.helper}</p>
              <div className="flex flex-col gap-2" style={{ marginLeft: 25 }}>
                {dataset.clarify.options.map((o) => (
                  <button
                    key={o.id}
                    onClick={() => { setDataset(KB[o.id]); setStage("done"); }}
                    style={{ fontSize: 14, border: `1px solid ${ink}`, color: ink, borderRadius: 4, padding: "10px 14px", background: "rgba(255,255,255,0.6)", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "space-between" }}
                  >
                    {o.label} <ArrowRight size={14} />
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {stage === "done" && (
          <div>
            <button onClick={reset} style={{ fontSize: 12.5, color: "#8b8570", background: "none", border: "none", cursor: "pointer", marginBottom: 16, fontFamily: sans }}>← New search</button>
            <ResultView data={dataset} onOpenStandard={setModalCode} />
            <div className="flex items-start gap-2 mt-6 pt-4" style={{ borderTop: `1px solid ${line}` }}>
              <Info size={14} style={{ color: "#8b8570", marginTop: 1, flexShrink: 0 }} />
              <p style={{ fontSize: 11.5, color: "#8b8570", fontFamily: sans }}>
                Illustrative data for this proof of concept. Always verify current status on the BIS portal before citing in a tender.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
