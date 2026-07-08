"""
03_plot_reads_vs_assembly.py
-----------------------------
Merges the QC-read counts (summary_samples_mqc.txt) and gene-recovery
information (summary_contigs_mqc.txt) to produce an interactive two-panel
HTML figure:

  Left panel  – Scatter: log₁₀(reads QC) vs unique canonical mitochondrial
                genes recovered, coloured by assembly outcome.
  Right panel – Strip chart: reads QC distribution per outcome category,
                jittered horizontally.  Median per category shown as a bar.

Usage
-----
    python scripts/03_plot_reads_vs_assembly.py

Input files
-----------
    data/summary_samples_mqc.txt   – per-sample read QC stats
    data/summary_contigs_mqc.txt   – per-contig assembly output

Output
------
    output/reads_vs_assembly.html

Gene counting
-------------
The assembler appends _0/_1/_2 (or -a/-b) to gene names when the same gene is
recovered across multiple contigs.  These suffixes are stripped before counting
so that each of the 15 canonical PCG/rRNA genes (cox1-3, nad1-6, nad4l, atp6,
atp8, cob, rrnL, rrnS) is counted at most once per sample.
"""

import csv
import json
import math
import re
from collections import defaultdict

SAMPLES_FILE = "data/summary_samples_mqc.txt"
CONTIGS_FILE = "data/summary_contigs_mqc.txt"
OUTPUT_FILE  = "output/reads_vs_assembly.html"

EXPECTED_GENES = {
    "cox1","cox2","cox3",
    "nad1","nad2","nad3","nad4","nad4l","nad5","nad6",
    "atp6","atp8","cob",
    "rrnL","rrnS",
}


def canonical_gene(name):
    """Strip _N and -[ab] suffixes to get the base gene name."""
    name = re.sub(r"_\d+$", "", name.strip())
    name = re.sub(r"-[ab]$", "", name)
    return name


def short_label(summary_id):
    """NCBN002890_A02_RMNH_INS_1719806  →  RMNH.INS.1719806"""
    return ".".join(summary_id.split("_")[2:])


# ── read QC counts ───────────────────────────────────────────────────────────
reads_qc = {}
with open(SAMPLES_FILE, newline="") as fh:
    for row in csv.DictReader(fh, delimiter="\t"):
        val = row["Reads QC"]
        reads_qc[row["ID"]] = int(val) if val != "NA" else None

# ── contig assembly: category + canonical gene set ───────────────────────────
contig_info = defaultdict(lambda: {"category": "fail", "genes": set()})

with open(CONTIGS_FILE, newline="") as fh:
    for row in csv.DictReader(fh, delimiter="\t"):
        sid    = row["ID"]
        contig = row["Contig"]
        genes  = row["Genes list"]

        if contig == "NA":
            pass
        elif "circular" in contig:
            contig_info[sid]["category"] = "circular"
        else:
            if contig_info[sid]["category"] != "circular":
                contig_info[sid]["category"] = "partial"

        if genes and genes != "NA":
            for g in genes.split(","):
                canon = canonical_gene(g)
                if canon in EXPECTED_GENES:
                    contig_info[sid]["genes"].add(canon)

# ── build merged record list ─────────────────────────────────────────────────
records = []
for sid, rqc in reads_qc.items():
    info        = contig_info.get(sid, {"category": "fail", "genes": set()})
    category    = info["category"]
    unique_genes = len(info["genes"])
    log_reads   = round(math.log10(rqc), 4) if rqc else None
    records.append({
        "id":           sid,
        "label":        short_label(sid),
        "reads_qc":     rqc,
        "log_reads":    log_reads,
        "category":     category,
        "unique_genes": unique_genes,
    })

print(f"Total samples: {len(records)}")
from collections import Counter
print("Category counts:", Counter(r["category"] for r in records))

# ── helpers for tooltip formatting ───────────────────────────────────────────
def fmt_reads(n):
    if n is None: return "N/A"
    if n >= 1e6:  return f"{n/1e6:.1f}M"
    if n >= 1e3:  return f"{n/1e3:.0f}k"
    return str(n)

# ── write HTML ───────────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Read quality vs mitogenome recovery</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
  :root {{
    --c-circular:#2a9d8f; --c-partial:#e9c46a; --c-fail:#e76f51;
  }}
  * {{ box-sizing:border-box; }}
  body {{
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    background:#fafaf8; color:#2b2b2b;
    margin:0; padding:28px 24px 52px;
  }}
  h1 {{ font-size:20px; font-weight:600; margin:0 0 4px; }}
  .sub {{ color:#666; font-size:13.5px; margin:0 0 28px; }}
  .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; max-width:1200px; margin:0 auto; }}
  .card {{
    background:#fff; border-radius:12px;
    padding:20px 20px 12px;
    box-shadow:0 1px 3px rgba(0,0,0,0.08);
  }}
  .card h2 {{ font-size:14px; font-weight:600; margin:0 0 4px; }}
  .card p  {{ font-size:12px; color:#666; margin:0 0 14px; }}
  .chart-wrap {{ position:relative; height:380px; }}
  .legend {{
    display:flex; gap:18px; justify-content:center;
    margin-top:14px; font-size:12.5px;
  }}
  .legend-item {{ display:flex; align-items:center; gap:6px; }}
  .dot {{ width:11px; height:11px; border-radius:50%; }}
  .note {{ max-width:1200px; margin:16px auto 0; font-size:12px; color:#999; text-align:center; }}
</style>
</head>
<body>
<h1>Read quality vs mitogenome recovery</h1>
<p class="sub">All {len(records)} samples · hover any point to see the sample ID and values</p>
<div class="grid">
  <div class="card">
    <h2>Reads QC vs unique mitochondrial genes recovered</h2>
    <p>X = log₁₀ reads passing QC; Y = distinct canonical mitochondrial genes (max 15: 13 PCGs + rrnL + rrnS).</p>
    <div class="chart-wrap"><canvas id="scatter"></canvas></div>
  </div>
  <div class="card">
    <h2>Reads QC distribution by assembly outcome</h2>
    <p>Each dot is one sample, jittered horizontally. Horizontal bar = median per category.</p>
    <div class="chart-wrap"><canvas id="strip"></canvas></div>
  </div>
</div>
<div class="legend">
  <div class="legend-item"><div class="dot" style="background:var(--c-circular)"></div> circular</div>
  <div class="legend-item"><div class="dot" style="background:var(--c-partial)"></div> partial</div>
  <div class="legend-item"><div class="dot" style="background:var(--c-fail)"></div> fail</div>
</div>
<p class="note">
  circular = complete circular mitogenome &nbsp;·&nbsp;
  partial = one or more linear contigs &nbsp;·&nbsp;
  fail = no contig assembled
</p>
<script>
const raw = {json.dumps(records)};
const COLORS = {{circular:"#2a9d8f", partial:"#e9c46a", fail:"#e76f51"}};

function fmt(n) {{
  if (!n) return "N/A";
  if (n>=1e6) return (n/1e6).toFixed(1)+"M";
  if (n>=1e3) return (n/1e3).toFixed(0)+"k";
  return ""+n;
}}

// ── scatter ──────────────────────────────────────────────────────────────────
new Chart(document.getElementById("scatter"), {{
  type:"scatter",
  data:{{
    datasets:["circular","partial","fail"].map(cat => ({{
      label:cat,
      data:raw.filter(d=>d.category===cat).map(d=>
        ({{x:d.log_reads, y:d.unique_genes, reads_qc:d.reads_qc, label:d.label}})),
      backgroundColor:COLORS[cat]+"cc",
      borderColor:COLORS[cat], borderWidth:1,
      pointRadius:6, pointHoverRadius:8
    }}))
  }},
  options:{{
    responsive:true, maintainAspectRatio:false,
    scales:{{
      x:{{ title:{{display:true,text:"Reads QC (log₁₀)"}}, min:4, max:7.8,
           ticks:{{callback:v=>({{4:"10k",5:"100k",6:"1M",7:"10M",7.6:"40M"}})[v]??""}} }},
      y:{{ title:{{display:true,text:"Unique mitochondrial genes"}}, min:-0.5, max:16,
           ticks:{{stepSize:5}} }}
    }},
    plugins:{{
      legend:{{display:false}},
      tooltip:{{
        callbacks:{{
          title:i=>i[0].raw.label,
          label:i=>[`Category: ${{i.dataset.label}}`,`Reads QC: ${{fmt(i.raw.reads_qc)}}`,`Unique genes: ${{i.raw.y}}`]
        }},
        backgroundColor:"rgba(20,20,20,0.92)", padding:10, displayColors:false,
        bodyFont:{{size:12}}, titleFont:{{size:13,weight:"600"}}
      }}
    }}
  }}
}});

// ── strip chart ──────────────────────────────────────────────────────────────
const catIdx = {{circular:0, partial:1, fail:2}};
function seededJitter(s, spread) {{
  let h=0; for(let i=0;i<s.length;i++) h=(Math.imul(31,h)+s.charCodeAt(i))|0;
  return ((h&0xffff)/0xffff-0.5)*spread;
}}

const stripChart = new Chart(document.getElementById("strip"), {{
  type:"scatter",
  data:{{
    datasets:["circular","partial","fail"].map(cat => ({{
      label:cat,
      data:raw.filter(d=>d.category===cat).map(d=>
        ({{x:catIdx[cat]+seededJitter(d.label,0.35), y:d.log_reads, reads_qc:d.reads_qc, label:d.label, cat}})),
      backgroundColor:COLORS[cat]+"bb",
      borderColor:COLORS[cat], borderWidth:1,
      pointRadius:6, pointHoverRadius:8
    }}))
  }},
  options:{{
    responsive:true, maintainAspectRatio:false,
    scales:{{
      x:{{ min:-0.6, max:2.6, grid:{{display:false}},
           ticks:{{callback:v=>(["circular","partial","fail"][Math.round(v)]??"")}} }},
      y:{{ title:{{display:true,text:"Reads QC (log₁₀)"}}, min:4, max:7.8,
           ticks:{{callback:v=>({{4:"10k",5:"100k",6:"1M",7:"10M",7.6:"40M"}})[v]??""}} }}
    }},
    plugins:{{
      legend:{{display:false}},
      tooltip:{{
        callbacks:{{
          title:i=>i[0].raw.label,
          label:i=>[`Category: ${{i.raw.cat}}`,`Reads QC: ${{fmt(i.raw.reads_qc)}}`]
        }},
        backgroundColor:"rgba(20,20,20,0.92)", padding:10, displayColors:false,
        bodyFont:{{size:12}}, titleFont:{{size:13,weight:"600"}}
      }}
    }}
  }},
  plugins:[{{
    id:"medianLines",
    afterDraw(chart) {{
      const {{ctx, scales:{{x,y}}}} = chart;
      ["circular","partial","fail"].forEach((cat,i) => {{
        const vals = raw.filter(d=>d.category===cat).map(d=>d.log_reads).sort((a,b)=>a-b);
        const mid  = Math.floor(vals.length/2);
        const med  = vals.length%2===0 ? (vals[mid-1]+vals[mid])/2 : vals[mid];
        const xPx  = x.getPixelForValue(i), yPx = y.getPixelForValue(med);
        ctx.save();
        ctx.strokeStyle=COLORS[cat]; ctx.lineWidth=2.5;
        ctx.beginPath(); ctx.moveTo(xPx-22,yPx); ctx.lineTo(xPx+22,yPx);
        ctx.stroke(); ctx.restore();
      }});
    }}
  }}]
}});
</script>
</body>
</html>"""

with open(OUTPUT_FILE, "w") as fh:
    fh.write(html)

print(f"Written {OUTPUT_FILE}")
