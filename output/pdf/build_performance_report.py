"""Build a shareable, six-page PDF from the pinned frozen-evaluation evidence.

Requires ReportLab, Pillow and pypdf. Uses native vector charts and lossless
source crops for display only; it never runs or edits recognition/evaluation.
"""
from pathlib import Path
import json
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from PIL import Image as PILImage, ImageDraw

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
COMMIT='4fbe781313add2c13ee86151c736282328cdd7bb'
BASE=f'https://github.com/marktgodfrey/sacredharp_omr/blob/{COMMIT}/'
PDF=OUT/'sacred-harp-omr-performance-2026-11-27.pdf'
DATA=json.loads((OUT/'performance-data.json').read_text())
FONT=Path('/System/Library/Fonts/Supplemental')
for n,f in [('Text','Arial.ttf'),('TextBold','Arial Bold.ttf'),('Title','Georgia.ttf')]:pdfmetrics.registerFont(TTFont(n,str(FONT/f)))
NAVY=colors.HexColor('#142E3F');TEAL=colors.HexColor('#087E83');ORANGE=colors.HexColor('#B65A29');GRAY=colors.HexColor('#536572');LIGHT=colors.HexColor('#EAF2F3');RULE=colors.HexColor('#D6E0E5');PAPER=colors.HexColor('#F4F7F8')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='BodyReport',fontName='Text',fontSize=9.4,leading=13.7,textColor=NAVY,spaceAfter=8))
styles.add(ParagraphStyle(name='SmallReport',fontName='Text',fontSize=8,leading=11,textColor=GRAY,spaceAfter=6))
styles.add(ParagraphStyle(name='HeadingReport',fontName='Title',fontSize=24,leading=29,textColor=NAVY,spaceAfter=13))
styles.add(ParagraphStyle(name='SubReport',fontName='TextBold',fontSize=12,leading=17,textColor=NAVY,spaceBefore=10,spaceAfter=6))
styles.add(ParagraphStyle(name='Eyebrow',fontName='TextBold',fontSize=8.5,leading=13,textColor=TEAL,spaceAfter=7))
styles.add(ParagraphStyle(name='CellReport',fontName='Text',fontSize=8.5,leading=11.5,textColor=NAVY))
styles.add(ParagraphStyle(name='CellHeadReport',fontName='TextBold',fontSize=8,leading=11,textColor=colors.white))
styles.add(ParagraphStyle(name='Cover',fontName='Title',fontSize=34,leading=39,textColor=NAVY,spaceAfter=18))
def P(t,style='BodyReport'):return Paragraph(t,styles[style])
def section(k,title):return [P(k.upper(),'Eyebrow'),P(title,'HeadingReport')]
def table(headers,rows,widths):
 data=[[P(str(x),'CellHeadReport') for x in headers]]+[[P(str(x),'CellReport') for x in row] for row in rows]
 t=Table(data,colWidths=widths,hAlign='LEFT',repeatRows=1)
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PAPER]),('LINEBELOW',(0,-1),(-1,-1),.6,RULE)]))
 return t

def cards(items):
 d=Drawing(504,84)
 for j,(big,label) in enumerate(items):
  x=j*172;d.add(Rect(x,0,160,80,fillColor=LIGHT,strokeColor=None));d.add(String(x+13,43,big,fontName='TextBold',fontSize=25,fillColor=TEAL));d.add(String(x+13,17,label,fontName='Text',fontSize=8.5,fillColor=NAVY))
 return d

def pd_chart():
 d=Drawing(504,126);x0=118;width=354;maximum=4000
 for tick in range(0,4001,1000):
  x=x0+width*tick/maximum;d.add(Line(x,23,x,111,strokeColor=RULE,strokeWidth=.5));d.add(String(x-6,8,str(tick),fontName='Text',fontSize=8,fillColor=GRAY))
 for y,label,val,col in [(81,'Previous checkpoint',3333,GRAY),(42,'Dot / head evidence',3312,TEAL)]:
  d.add(String(0,y+9,label,fontName='Text',fontSize=9,fillColor=NAVY));d.add(Rect(x0,y,width*val/maximum,23,fillColor=col,strokeColor=None));d.add(String(x0+width*val/maximum+6,y+7,str(val),fontName='TextBold',fontSize=9,fillColor=NAVY))
 return d

def severe_chart():
 d=Drawing(504,174);x0=110;width=315;scale=width/3
 for tick in range(4):
  x=x0+tick*scale;d.add(Line(x,24,x,166,strokeColor=RULE,strokeWidth=.5));d.add(String(x-2,7,str(tick),fontName='Text',fontSize=8,fillColor=GRAY))
 for j,(name,total,notes) in enumerate([('Triangle',2,1),('Oval',2,2),('Square',3,1),('Diamond',3,2)]):
  y=135-j*34;d.add(String(0,y+7,name,fontName='TextBold',fontSize=9,fillColor=NAVY));d.add(Rect(x0,y,notes*scale,22,fillColor=TEAL,strokeColor=None));d.add(Rect(x0+notes*scale,y,(total-notes)*scale,22,fillColor=colors.HexColor('#E4BD9E'),strokeColor=None));d.add(String(x0+total*scale+7,y+7,f'{notes}/{total}',fontName='TextBold',fontSize=9,fillColor=NAVY))
 return d

def source_figures():
 S=ROOT/'benchmarks/crossbook-frozen-rules/source-sets/severe-four-shape-holdout-20261126/pages'
 figs=[]
 for name,n,crop,box in [('A03-fragmented-triangle',35,(565,548,690,654),(614,590,646,616)),('A10-fragmented-diamond',47,(1525,92,1650,198),(1573,129,1603,159))]:
  path=OUT/(name+'.png')
  source=S/f'1835-render-{n:03}.png'
  if source.exists():
   im=PILImage.open(source).convert('RGB').crop(crop);dr=ImageDraw.Draw(im);dr.rectangle([box[0]-crop[0],box[1]-crop[1],box[2]-crop[0],box[3]-crop[1]],outline=(20,120,150),width=1);im.save(path)
  if not path.exists():raise FileNotFoundError('Missing source page and bundled report figure: '+str(path))
  figs.append(Image(str(path),width=230,height=195))
 return figs

def footer(c,doc):
 c.setStrokeColor(TEAL);c.setLineWidth(3);c.line(54,749,558,749)
 c.setFont('Text',8);c.setFillColor(GRAY);c.drawString(54,32,'Sacred Harp OMR | Frozen-rule review | 27 November 2026');c.drawRightString(558,32,f'{doc.page} / 6')
 c.setTitle('Sacred Harp OMR - rule improvements and frozen transfer results');c.setAuthor('Sacred Harp OMR research project');c.setSubject('Performance, source-first holdouts, failures and limits of frozen shape-note OMR rules')

story=[]
story += [Spacer(1,17),P('RESEARCH PROGRESS / PERFORMANCE REVIEW','Eyebrow'),P('Sacred Harp OMR','Cover'),P('Rule improvements and<br/>frozen transfer results','HeadingReport'),P('27 November 2026 | Evidence pinned to GitHub commit <b>4fbe781</b>','SmallReport'),Spacer(1,10),cards([('120','songs in development batch'),('85','edition-crops in later cohorts'),('6 / 10','severe heads become notes')]),Spacer(1,18),P('Source-grounded rules improve development reference agreement. Cross-printing tests expose recognition, layout and duplicate-note failures that still limit broader use.','SubReport'),P('The work adds evidence for augmentation dots, repeat dots, beams and false noteheads, then makes head rejection conservative when unexplained source ink remains. Frozen tests preserve both successes and negative results. Production defaults and the gallery remain unchanged.'),table(['Finding','Interpretation'],[
('21 fewer pitch-duration edits','Development disagreement decreases from 3,333 to 3,312 (0.63%). This is reference agreement on observed development material.'),
('Four severe head shapes covered','In Southern Harmony, six of ten premarked severe heads become notes in every version. Four fail before the new safeguard can help.'),
('Transfer remains conditional','Scored outcomes vary by printing and layout. The latest batch has wrong system grouping in six of eight tunes; retained duplicates and reviewer disputes remain explicit.')],[147,357]),Spacer(1,10),P('Read the figures as selected-sample results. The cohorts are not random book-wide samples, paired layouts are not independent heads, and model training provenance is unknown.','SmallReport')]
story.append(PageBreak())
# Page 2
story += section('01 / What changed','General evidence rules, then conservative rejection')
story += [table(['Change','Purpose and evidence'],[
('Dots and repeat context','Separate augmentation-dot evidence from vertical repeat-dot columns; retain distinct real dots beside repeats. Use source geometry and relative contrast.'),
('False-head evidence','Use attached stem/beam and repeat-dot context to identify non-head interpretations. Preserve source IDs for actual serialized notes.'),
('Damaged-head abstention','Reject a broad line/blemish candidate only when supported thin staff lines explain its ink completely. Any unexplained fragment makes that rule abstain. Narrow empty-box/repeat/beam rules remain unchanged.')],[143,361]),P('Development batch: 120 songs','SubReport'),pd_chart(),P('Pitch-duration edit disagreement, lower is better; zero-based scale. The dot/head checkpoint (b651) is compared with the previous rhythm checkpoint (final-a174).','SmallReport'),table(['Cohort','PD edits, previous → b651','Time-aware exact-event F1'],[
('Development','2,712 → 2,694','0.6640 → 0.6919'),('Diagnostic','621 → 618','0.6637 → 0.6642'),('Combined','3,333 → 3,312','Not pooled across these cohorts')],[115,187,202]),Spacer(1,8),P('<b>Distribution:</b> PD better / tied / worse: <b>13 / 106 / 1</b> songs. Timing better / tied / worse: <b>17 / 102 / 1</b>. Unresolved columns decrease from <b>87 to 80 of 2,104</b>.'),P('Fillmore is the sole new scored regression (+1 PD edit). Elder column 8 remains flagged with its real dot/head retained. Development controls protect 18 reviewed heads and 17 durations; source/reference disagreements remain unresolved. [1]','SmallReport')]
story.append(PageBreak())
# Page3 tables supplied by statistics extraction, no inferred pooled F1.
story += section('02 / Scored cross-printing tests','Reference agreement varies across sources')
story += [P('<b>Metric key.</b> PD is pitch-duration edit disagreement with a reference edition; lower is better. F1 is time-aware exact-event agreement; higher is better. PD cells show edits / scoring denominator, not accuracy percentages. Reference editions can disagree with visible historical source notation.'),P('Expanded 52 edition-crops: 1870 MTS and J. L. White 1911 EMU','SubReport'),P('Default and cleaned (clean_layout) reader variants; final-a174 prior versus dot/head b651 current. The 14-crop pilot overlaps this expanded cohort and is not added to the sample total.','SmallReport')]
story += [table(['Printing / layout','Baseline PD','Prior PD','b651 PD','Δ PD','F1 baseline / prior / b651'],DATA['expanded_rows'],[125,64,61,61,49,144]),P('Positive Δ PD means more reference disagreement. The source audit found a genuine Aylesbury head rejected by the broader prior dot/head logic, motivating the later conservative abstention revision. Selected Kedron localization also remained unresolved. Sixteen of 104 configurations fail equal spans in both policies (14 default, 2 cleaned). PD better / tied / worse: 11 / 92 / 1. All failures remain included. [2]','SmallReport'),P('Untouched 1860 cohort: 19 edition-crops / 38 configurations','SubReport'),P('Here the comparison changes: dot/head b651 prior versus conservative c291 current. Do not compare these differences as if the policy pair were identical to the expanded 52-crop experiment.','SmallReport'),table(['Layout','Baseline PD','b651 PD','c291 PD','Δ PD','F1 baseline / b651 / c291'],DATA['1860_rows'],[125,64,61,61,49,144]),P('<b>Cost:</b> conservative abstention retains four artifact objects across the two layouts (eight abstention observations); total PD disagreement rises by <b>7 edits</b>. No genuine held-out damaged head exercises the new protection in this cohort.'),P('Three configurations retain unequal part spans in both policies: Hallelujah in both layouts and Ocean in default layout. The native baseline has higher F1 than either full applied rhythm stage in this sample. These are preserved negative results. [3]','SmallReport')]
story.append(PageBreak())
# Page4
story += section('03 / Source-first damaged heads','Coverage is broader; recognition still limits survival')
story += [P('1850 Auburn / VEMP: six complete tunes','SubReport'),P('A predeclared 40-page screen selected three likely damaged heads and one disputed secondary case. All <b>3/3 likely damaged heads</b> become notes in baseline, b651 and c291, in both layouts. The safeguard never triggers: all 12 prior/current XML pairs are byte-identical. One of eight intact controls is serialized as a rest; Distress loses a staff. This establishes selected-head survival, not rescue by the fix. [4]'),P('1835 Southern Harmony: eight complete tunes','SubReport'),P('The next finite screen covered 300 new 1850 PDF pages with no qualifying cases, excluded the seven-shape 1884 book, then inspected 80 available Southern Harmony music pages. Printed pages 31-32 are absent. Source labels/crops were locked before inference. [5]'),severe_chart(),P('<font color="#087E83">■</font> Serialized note in baseline, b651 and c291 &nbsp;&nbsp; <font color="#B65A29">■</font> No serialized baseline note<br/>Distinct severe heads; paired layouts are not counted twice. Missing output is a failure, not a protection success.','SmallReport'),table(['Locked cohort','Objects','Notes, each version','Interpretation'],[
('Severe damage','10','6','Two squares matched but not serialized; one triangle and one diamond unmatched.'),('Moderate damage','9','7','Two matched candidates are not serialized as notes.'),('Ambiguous, separate','5','3','Excluded from primary shape/severity claims.'),('Intact controls','38','29','Includes rest-class errors, unmatched heads and an oversized match.')],[136,53,113,202]),Spacer(1,8),P('No premarked baseline-emitted head is newly lost, but no premarked head exercises the revised abstention. Retention does not certify shape, pitch, voice or duration.','SmallReport')]
story.append(PageBreak())
#Page5
story += section('04 / Failures retained','The report includes what the pipeline misses')
f=source_figures();it=Table([f],colWidths=[252,252]);it.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0)]));story.append(it)
story += [table(['A03 / Liverpool, printed page 1','A10 / Dublin, printed page 13'],[['Fragmented triangle: no matching front-end note/rest under the locked matching rule, in either layout.','Fragmented diamond: no matching front-end note/rest under the locked matching rule, in either layout.']],[252,252]),P('Source examples from the fixed 300 dpi Southern Harmony composite, enlarged for display only; blue boxes identify the source objects. Original scan: Oberlin College Library / Internet Archive. [5]','SmallReport'),table(['Latest-batch failure','Observed result'],[
('System grouping','Wrong in 6/8 tunes, both layouts: Invitation, Meditation, Hanover, Salem, Dublin and Devotion. All individual staves were found, but voices were split into incorrect systems.'),
('Timing invariant','Dublin has 36 unequal-span columns in both versions/layouts (2/16 configurations). Other passes can be vacuous after one-staff splitting.'),
('Extra notes and cut expansions','The current policy retains six clear new shifted duplicates/artifacts in the main review. Salem cut lengths expand 6 → 7.5 and 6 → 7; Devotion 9 → 11, in each layout.'),
('Exploratory recoveries','15 unique abstentions: main review supports six possible real-head recoveries; independent review supports head presence for two and disputes/cannot establish four. Two other mislocalized associations remain uncertain; one duplicate already existed.')],[137,367]),P('All exploratory judgments remain separate from the locked primary labels. A source fragment, a note-class detector symbol and an actually emitted note are three different levels of evidence. [5]','SmallReport')]
story.append(PageBreak())
#Page6
story += section('05 / Interpretation and reproducibility','Keep the rules experimental and reserve fresh evidence')
story += [P('What reduces overfitting risk','SubReport'),P('The rules use source ink and staff-space geometry, with no tune-title or case-ID exception. Frozen snapshots, fixed meter banks and hash guards precede target inference. Within each evaluation, labels/crops and rules stay fixed after inference. The earlier Aylesbury failure informed the next revision and became development material; new samples then tested that revision. All stage failures remain represented.'),P('What remains missing','SubReport'),P('The severe cohort has only two ovals and two triangles against the three-per-shape ceiling; moderate diamonds are absent. Severe ovals/diamonds are hollow only, squares filled only, and triangles have one of each fill. Several intact-control cells are missing. Exact globally first-three eligible-head ordering could not be certified, and an extra control-only page was retained: both weaken strict preregistration.'),P('Selection is enriched and partly convenience-based. Some moderate/control labels have only one reviewer. Shared repertoire/possible printing ancestry and unknown model training provenance limit independence. Source ink loss may arise from printing, scanning or layered-PDF compression; physical cause is not established.'),table(['Record','Verification'],[
('Evaluation scope','85 selected edition-crops in the expanded 52 + 1860 19 + 1850 6 + Southern Harmony 8 cohorts; 170 paired-layout configurations and 510 stage cases. These are not 85 independent tunes.'),
('Frozen integrity','Latest run: 1,325 artifact hashes verified; older seals: 534 / 737 / 1,334 / 594. Historical c291 rule validation records 214 tests; pre-push targeted checks passed 27 rule tests plus 4 adapter tests.'),
('Availability','Commit 4fbe781 includes fixes, frozen source snapshots/templates and compact evidence. Raw PDFs, native crops and full prediction trees remain local; the earlier release does not contain all new data. [6]')],[137,367]),P('<b>Recommended:</b> develop recognition/system grouping and duplicate handling using these observed failures, then validate any revision on a newly selected source-first holdout. <b>Alternative:</b> keep both engines frozen and expand independently adjudicated missing shape/fill coverage.','BodyReport'),P('Evidence links (pinned to the pushed commit)','SubReport')]
for num,title,path in [
(1,'120-song development comparison','benchmarks/sacred-harp-1911/experiments/rhythm-resolution/dot-head-evidence-20261126-b6512a5f402d/COMPARISON.md'),
(2,'Expanded 52-crop report','benchmarks/crossbook-frozen-rules/runs/expanded52-frozen-dot-head-20261126/REPORT.md'),
(3,'1860 conservative-abstention report','benchmarks/crossbook-frozen-rules/runs/1860-abstention-holdout-20261126/REPORT.md'),
(4,'1850 source-first damaged-head review','benchmarks/crossbook-frozen-rules/runs/1850-damaged-head-holdout-20261126/SOURCE_REVIEW.md'),
(5,'Southern Harmony severe-damage report and limits','benchmarks/crossbook-frozen-rules/runs/severe-four-shape-holdout-20261127/REPORT.md'),
(6,'Committed evidence and local artifact-data scope','benchmarks/crossbook-frozen-rules/ARTIFACTS.md')]:
 story.append(P(f'[{num}] <link href="{BASE+path}" color="#087E83">{escape(title)}</link>','SmallReport'))

doc=SimpleDocTemplate(str(PDF),pagesize=(612,792),rightMargin=54,leftMargin=54,topMargin=58,bottomMargin=50,allowSplitting=1)
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(PDF)
