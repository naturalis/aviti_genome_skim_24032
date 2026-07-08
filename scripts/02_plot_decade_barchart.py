"""
02_plot_decade_barchart.py
--------------------------
Reads the merged result table produced by 01_merge_ids.py and generates an
interactive stacked bar chart (HTML / Chart.js) showing assembly outcome
(circular / partial / fail) per collection decade.

Hovering over a bar segment shows the sample IDs in that group.

Usage
-----
    python scripts/02_plot_decade_barchart.py

Input
-----
    output/contig_year_summary.xlsx

Output
------
    output/contig_result_by_decade.html

Category mapping
----------------
    "circular"         → circular   (complete circular mitogenome)
    starts with "contig" → partial  (one or more linear contigs)
    "NA"               → fail       (no contig assembled)
"""

import csv
import json
import re
import openpyxl
from collections import defaultdict

INPUT_FILE  = "output/contig_year_summary.xlsx"
OUTPUT_FILE = "output/contig_result_by_decade.html"

COLORS = {"circular": "#2a9d8f", "partial": "#e9c46a", "fail": "#e76f51"}


# ── load merged table ────────────────────────────────────────────────────────
wb = openpyxl.load_workbook(INPUT_FILE)
ws = wb.active

rows_with_year = []
for row in ws.iter_rows(min_row=2, values_only=True):
    specimen_id, result, year = row[0], row[1], row[2]
    if not str(year).lstrip("-").isdigit():
        continue
    year = int(year)
    if result == "NA":
        cat = "fail"
    elif str(result).startswith("circular"):
        cat = "circular"
    else:
        cat = "partial"
    rows_with_year.append((specimen_id, cat, (year // 10) * 10))

print(f"Samples with valid year: {len(rows_with_year)}")

# ── aggregate per decade ─────────────────────────────────────────────────────
decades_data = defaultdict(lambda: {"circular": [], "partial": [], "fail": []})
for sid, cat, decade in rows_with_year:
    decades_data[decade][cat].append(sid)

decades = sorted(decades_data.keys())
payload = [
    {
        "decade":   d,
        "circular": decades_data[d]["circular"],
        "partial":  decades_data[d]["partial"],
        "fail":     decades_data[d]["fail"],
    }
    for d in decades
]

# ── render HTML ──────────────────────────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Contig result by collection decade</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #fafaf8; color: #2b2b2b;
    margin: 0; padding: 32px 24px 48px;
  }}
  .wrap {{ max-width: 960px; margin: 0 auto; }}
  h1 {{ font-size: 20px; font-weight: 600; margin: 0 0 4px; }}
  p.sub {{ margin: 0 0 28px; color: #666; font-size: 14px; }}
  .card {{
    background: #fff; border-radius: 12px;
    padding: 20px 20px 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  }}
  .chart-wrap {{ position: relative; height: 500px; }}
  .note {{ margin-top: 14px; font-size: 12.5px; color: #888; text-align: center; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>Contig assembly result by collection decade</h1>
  <p class="sub">
    Hover over a segment to see the sample IDs it contains.
    n = {len(rows_with_year)} samples with a known collection year
    (3 samples with unknown year excluded).
  </p>
  <div class="card">
    <div class="chart-wrap"><canvas id="chart"></canvas></div>
  </div>
  <p class="note">
    circular = complete circular mitogenome &nbsp;·&nbsp;
    partial = one or more linear contigs assembled &nbsp;·&nbsp;
    fail = no contig assembled
  </p>
</div>
<script>
const data = {json.dumps(payload)};
const labels = data.map(d => d.decade + "s");
const circ = data.map(d => d.circular.length);
const part = data.map(d => d.partial.length);
const fail = data.map(d => d.fail.length);
const ids  = {{ circular: data.map(d => d.circular),
               partial:  data.map(d => d.partial),
               fail:     data.map(d => d.fail) }};

function wrapIds(arr, n=3) {{
  const lines = [];
  for (let i=0; i<arr.length; i+=n) lines.push(arr.slice(i,i+n).join(", "));
  return lines;
}}

new Chart(document.getElementById("chart"), {{
  type: "bar",
  data: {{
    labels,
    datasets: [
      {{ label:"circular", data:circ, backgroundColor:"{COLORS['circular']}", key:"circular" }},
      {{ label:"partial",  data:part, backgroundColor:"{COLORS['partial']}",  key:"partial"  }},
      {{ label:"fail",     data:fail, backgroundColor:"{COLORS['fail']}",     key:"fail"     }}
    ]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    scales: {{
      x: {{ stacked:true, grid:{{display:false}},
            title:{{display:true, text:"Collection decade"}} }},
      y: {{ stacked:true, beginAtZero:true,
            ticks:{{precision:0}},
            title:{{display:true, text:"Number of samples"}} }}
    }},
    plugins: {{
      legend: {{ position:"top" }},
      tooltip: {{
        callbacks: {{
          title: items => `${{items[0].label}} — ${{items[0].dataset.label}} (n=${{items[0].raw}})`,
          label: item  => wrapIds(ids[item.dataset.key][item.dataIndex])
        }},
        backgroundColor:"rgba(20,20,20,0.92)",
        padding:10, displayColors:false,
        titleFont:{{size:13,weight:"600"}}, bodyFont:{{size:12}}
      }}
    }}
  }}
}});
</script>
</body>
</html>"""

with open(OUTPUT_FILE, "w") as fh:
    fh.write(html)

print(f"Written {OUTPUT_FILE}")
