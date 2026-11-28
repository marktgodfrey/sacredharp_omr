"""Build the plain-language project overview; does not run or alter OMR.

Run with the bundled Python runtime (ReportLab, Pillow, pypdf).
The small example images are bundled beside the PDF for repeatable builds.
"""
from pathlib import Path
from xml.sax.saxutils import escape
import hashlib
import json

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image,
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
from pypdf import PdfReader

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
PDF = OUT / 'sacred-harp-omr-project-overview.pdf'
ACCURACY = json.loads((OUT / 'overview-accuracy-data.json').read_text())
PAGE_COUNT = 8
FONT = Path('/System/Library/Fonts/Supplemental')
for name, filename in [('Body', 'Arial.ttf'), ('Bold', 'Arial Bold.ttf'), ('Display', 'Georgia.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(FONT / filename)))
pdfmetrics.registerFontFamily('Body', normal='Body', bold='Bold', italic='Body', boldItalic='Bold')

INK = colors.HexColor('#172E3A')
TEAL = colors.HexColor('#087A78')
MUTED = colors.HexColor('#50636C')
LIGHT = colors.HexColor('#EDF5F4')
WARM = colors.HexColor('#FCF1E6')
ORANGE = colors.HexColor('#AD5525')
WIDTH = 500
STYLES = {
    'body': ParagraphStyle('body', fontName='Body', fontSize=12, leading=17, textColor=INK, spaceAfter=10),
    'small': ParagraphStyle('small', fontName='Body', fontSize=10, leading=14, textColor=MUTED, spaceAfter=8),
    'title': ParagraphStyle('title', fontName='Display', fontSize=29, leading=34, textColor=colors.black, spaceAfter=17),
    'heading': ParagraphStyle('heading', fontName='Bold', fontSize=14, leading=19, textColor=INK, spaceBefore=9, spaceAfter=7),
    'label': ParagraphStyle('label', fontName='Bold', fontSize=9, leading=12, textColor=TEAL, spaceAfter=10),
    'cell': ParagraphStyle('cell', fontName='Body', fontSize=11.2, leading=14.5, textColor=INK),
    'cellhead': ParagraphStyle('cellhead', fontName='Bold', fontSize=11.2, leading=14.5, textColor=INK),
}

def p(text, style='body'):
    return Paragraph(text, STYLES[style])

def table(rows, widths, header=False):
    cells = [[p(c, 'cellhead' if header and i == 0 else 'cell') for c in row] for i, row in enumerate(rows)]
    t = Table(cells, colWidths=widths, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 11), ('RIGHTPADDING', (0, 0), (-1, -1), 11),
        ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [LIGHT, colors.white]),
    ]))
    return t

def box(text, warm=False):
    t = Table([[p(text)]], colWidths=[WIDTH])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), WARM if warm else LIGHT),
        ('LEFTPADDING', (0, 0), (-1, -1), 14), ('RIGHTPADDING', (0, 0), (-1, -1), 14),
        ('TOPPADDING', (0, 0), (-1, -1), 12), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return t

story = []
def page(number, title):
    if story:
        story.append(PageBreak())
    story.extend([p(f'PROJECT OVERVIEW  /  {number:02d}', 'label'), p(title, 'title')])

def heading(title, text):
    story.extend([p(title, 'heading'), p(text)])

def pipeline():
    d = Drawing(WIDTH, 107)
    labels = [('Scan', 'A picture of the page'), ('Read', 'Find and interpret marks'), ('MusicXML', 'An editable music file')]
    for i, (title, sub) in enumerate(labels):
        x = i * 174
        d.add(Rect(x, 16, 152, 76, fillColor=LIGHT, strokeColor=None))
        d.add(String(x+12, 63, title, fontName='Bold', fontSize=16, fillColor=TEAL))
        d.add(String(x+12, 38, sub, fontName='Body', fontSize=9, fillColor=INK))
        if i < 2:
            d.add(Line(x+157, 54, x+168, 54, strokeColor=TEAL, strokeWidth=2))
            d.add(Polygon([x+165, 58, x+170, 54, x+165, 50], fillColor=TEAL, strokeColor=None))
    return d

def progress_chart():
    d = Drawing(WIDTH, 167)
    values = [('Earlier research version', 5931), ('Better ink and note checks', 5686),
              ('Search again for missed notes', 5021), ('Repair grouping and rhythm', 3650),
              ('Later rhythm and dot fixes', 3312)]
    x0, scale = 205, 250 / 6000
    for i, (label, value) in enumerate(values):
        y = 135-i*26
        d.add(String(0, y+7, label, fontName='Body', fontSize=10, fillColor=INK))
        d.add(Rect(x0, y, value*scale, 21, fillColor=TEAL if i == 4 else colors.HexColor('#A8C9C7'), strokeColor=None))
        d.add(String(x0+value*scale+6, y+6, f'{value:,}', fontName='Bold', fontSize=10, fillColor=INK))
    d.add(Line(x0, 19, x0+250, 19, strokeColor=MUTED, strokeWidth=.5))
    for tick in (0, 2000, 4000, 6000):
        x=x0+tick*scale
        d.add(String(x-7, 5, f'{tick:,}', fontName='Body', fontSize=9, fillColor=MUTED))
    return d

def damage_chart():
    d=Drawing(WIDTH, 60)
    for i in range(10):
        d.add(Rect(i*48, 17, 36, 30, fillColor=TEAL if i<6 else colors.HexColor('#E8BC99'), strokeColor=None))
    d.add(String(0, 0, '6 became notes', fontName='Bold', fontSize=11, fillColor=TEAL))
    d.add(String(288, 0, '4 did not become notes', fontName='Bold', fontSize=11, fillColor=ORANGE))
    return d

def example_images():
    target=OUT/'overview-recovered-square.png'
    source=ROOT/'benchmarks/sacred-harp-1911/experiments/missing-proposals/final-d190393b6a83/recovered-18.jpg'
    if not target.exists():
        im=PILImage.open(source)
        im.crop((235, 45, 565, 535)).save(target)
    success=Image(str(target), width=111, height=165)
    failure=Image(str(OUT/'A03-fragmented-triangle.png'), width=194, height=165)
    t=Table([[success, failure]], colWidths=[250,250])
    t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
    return t

page(1, 'Reading four shape tunebooks with OMR')
story.append(p('What this project has built and what still needs work', 'heading'))
story.append(p('27 November 2026', 'small'))
story.append(p('The goal is to turn scans of old four shape tunebooks into editable music. OMR means <b>optical music recognition</b>: software tries to read a picture of printed music, much as text recognition reads a photograph of a book.'))
story.append(pipeline())
story.append(box('<b>We can produce MusicXML, but it still needs substantial human correction.</b> At the measured checkpoint, there were about 14 pitch or note-length comparison edits per 100 note entries. Page 4 explains what that means.'))
heading('How close are we', 'The scan-to-file path already works. The hard remaining job is making the music inside the file trustworthy: the right notes, pitches, lengths, voice parts and timing. A file that opens successfully can still contain serious musical mistakes.')
story.append(table([
    ['Already demonstrated', 'Scan reading, MusicXML export, shape-note display, and substantial improvements on the development songs.'],
    ['Useful with human checking', 'Draft transcriptions and focused experiments on selected tunes. The amount of correction needed varies greatly.'],
    ['Still to prove', 'Reliable reading across different books, damaged printing, unusual layouts, and complete songs with few corrections.'],
], [157,343]))
story.append(Spacer(1,8))
story.append(p('There is no defensible percentage complete or finish date yet. The tests show real progress, but also failures that require more than small cleanup changes. [1-8]', 'small'))

page(2, 'What Copisteria gives us right away')
story.append(p('<b>Copisteria supplies the basic music-reading engine.</b> The project starts from KobiMusic\'s existing software and trained models, so we do not have to build an OMR system from scratch. [1]'))
story.append(table([
    ['Part of the engine', 'What it does in everyday language'],
    ['Symbol finder', 'Looks for noteheads, stems, rests, bar lines and other marks in an image or PDF page.'],
    ['Context reader', 'Uses nearby music to help decide what each mark means, including pitch, rhythm and voice.'],
    ['MusicXML writer', 'Puts the reading into a standard file that music software can open and edit.'],
    ['Inspection tools', 'Shows the scan with detected symbols and a rendered score, so mistakes can be traced.'],
], [148,352], header=True))
heading('What this project adds', 'The Sacred Harp work adds checks against the actual scan, a second search for missed notes, repairs to voice grouping and timing, and tests on historical tunebooks. It also adds four shape output, Apple CoreML support and a native iOS reader prototype. [2-8]')
heading('A stronger reader around existing models', 'The improvements reported here mainly change how the existing models are used and how their readings are checked. They do not demonstrate a newly trained four shape recognition model. A future training effort could build on the collected examples.')
story.append(box('<b>Shape-note output is only one part of accuracy.</b> Software can assign fa, sol, la and mi shapes from a note\'s scale position. If the pitch, key or mode was read wrongly, a neat shape-note score can still be wrong. [2]', warm=True))
story.append(Spacer(1,8))
story.append(p('The optional four-staff arranger can also change key, octave and voice placement. That is a musical arrangement, so its output needs a separate check from a faithful transcription. The iOS prototype demonstrates integration; desktop results do not establish phone-camera accuracy. [2]', 'small'))

page(3, 'Which improvements are working')
story.append(p('Several stages together have made the development results much better. The chart follows the same 120 songs from an earlier research version through the later dot and rhythm checkpoint. These songs were used to develop or diagnose the fixes. [3-6]'))
story.append(p('Fewer disagreements means a better match', 'heading'))
story.append(progress_chart())
story.append(p('<b>5,931 down to 3,312</b> is about 44% fewer comparison edits. The final count is <b>3,312 out of 23,988, or 13.8%</b>. This starts at an earlier research checkpoint, not untouched Copisteria, and ends before the later conservative safeguard. It is not a 44-point increase in accuracy.', 'small'))
story.append(table([
    ['Improvement', 'The trick and the evidence'],
    ['Look through staff lines', 'Remove only clearly supported thin line ink when checking a head. In a selected 95-head problem sample, the local recovery stages raised heads written as notes from 9 to 35. [3]'],
    ['Search a missed spot again', 'Recheck small image crops at several sizes when a note may have been mistaken for a rest. A later stage recovered all 18 selected problem heads. [4]'],
    ['Repair grouping and timing', 'Keep parallel singing parts together and use visible stems, beams and meter signs. Across the staged work, all 17 checkable durations in the reviewed 18-head set were corrected. [5-6]'],
    ['Separate dots from dirt', 'Use position and nearby ink to distinguish rhythm dots, repeat dots and false heads. The dot/head step cut edits from 3,333 to 3,312; 13 songs improved, 106 tied and one worsened. [6]'],
], [140,360], header=True))
story.append(Spacer(1,5))
story.append(p('These small reviewed sets show specific repairs, not overall note accuracy. Recovering a notehead alone does not prove its pitch, duration or voice is correct.', 'small'))

page(4, 'What 3312 disagreements means')
story.append(p('<b>This is meaningful research progress, but too much disagreement for dependable finished scores.</b> Today, the best description is a draft generator that needs careful human proofreading.'))
story.append(table([
    ['What was measured', 'Result'],
    ['Songs tested', f'{ACCURACY["songs"]} development and diagnostic songs'],
    ['Note entries used as the comparison total', f'{ACCURACY["comparison_denominator"]:,}'],
    ['Pitch or note-length comparison edits', f'{ACCURACY["pitch_duration_edits"]:,}'],
    ['Disagreement rate', f'<b>{ACCURACY["disagreement_percent"]:.1f}%</b>'],
], [335,165], header=True))
story.append(Spacer(1,8))
story.append(p('That is <b>about 14 comparison edits per 100 note entries</b>, or <b>28 per song on average</b>. An edit inserts a missing note, deletes an extra note, or changes its pitch or length. The total uses whichever has more notes, reference or prediction, for each voice part.'))
story.append(p('Some songs are much closer than others', 'heading'))
story.append(table([
    ['Disagreement within a song', 'Number of songs'],
    ['Less than 5%', str(ACCURACY['song_bands']['under_5_percent'])],
    ['5% to less than 20%', str(ACCURACY['song_bands']['5_to_under_20_percent'])],
    ['20% or more', str(ACCURACY['song_bands']['20_percent_or_more'])],
], [335,165], header=True))
story.append(Spacer(1,8))
story.append(p('<b>None of the 120 songs matched the reference perfectly.</b> That does not prove every song was read wrongly: the references are a different edition, so some differences may be legitimate.'))
story.append(box('<b>This does not mean 86.2% accurate.</b> The count does not fully check lyrics, repeats, ties, shape meanings, or when notes occur. These familiar development songs also do not establish reliability on other books.', warm=True))
story.append(Spacer(1,8))
story.append(p('<b>Recommended:</b> proofread 10-20 complete tunes against their scans and measure actual errors and correction time. <b>Alternative:</b> use current drafts and record corrections during normal proofreading. [6]', 'small'))

page(5, 'Two examples from the scans')
story.append(p('Enlarged scan details show a recovered note and a missed note. The boxes are display annotations; they were not fed into recognition.'))
story.append(example_images())
story.append(table([
    ['A recovered square note', 'A badly broken triangle'],
    ['Repentance from the 1911 Sacred Harp. The boxed square is a real printed note that needed a second search before it appeared as a note in the output. It is one of the 18 reviewed recoveries. [4]', 'Liverpool from Southern Harmony, catalogued 1835. The boxed triangle is so broken that the test found no corresponding note or rest candidate. Every tested version missed it. [8]'],
], [250,250], header=True))
heading('Finding a head is only the first step', 'The square shows that a second look can recover a missed note. The triangle shows a limit: a later safeguard cannot protect something the earlier stages never found. Neither picture proves a correct complete song.')
heading('Why tiny dots matter', 'An ordinary rhythm dot adds half of a note\'s value. For example, a two-beat note becomes three beats. Mistaking a nearby repeat dot or stain for that dot can add a beat and push later music out of time.')
story.append(box('<b>A sensible rule can still go too far.</b> One earlier false-head filter deleted a genuine damaged note in another printing. The revision now holds back when unexplained ink might be part of a real head. That protects uncertain marks, but can also keep dirt and duplicate notes. [7-8]', warm=True))

page(6, 'What happens on other books')
story.append(p('<b>The improvements do not yet work reliably everywhere.</b> Later tests used rules that were fixed before the new runs. Results varied by printing and by the way the page layout was read. [7-8]'))
story.append(table([
    ['Test', 'What we learned'],
    ['1870 and another 1911 printing', '26 tunes per printing. Some comparisons improved, but 1911 results with page cleanup worsened versus the basic reader. In 16 of 104 layout runs, voice parts ended at different times.'],
    ['1860 Sacred Harp', '19 crops in two layout modes. The cautious safeguard kept four false objects, such as dirt or extra note interpretations, and added seven comparison edits. No new damaged-head rescue was shown.'],
    ['1850 Sacred Harp', 'Six tunes on four pages. All three primary damaged heads became notes in every version. The safeguard never triggered, so it gets no credit for rescuing them.'],
], [145,355], header=True))
heading('The hardest four shape sample still exposes large gaps', 'In eight selected Southern Harmony tunes, only <b>6 of 10 severely damaged heads</b> became notes. The same six survived in every tested version. Two squares had candidates but no final note; a triangle and diamond had no matching candidate. [8]')
story.append(damage_chart())
story.append(Spacer(1,9))
story.append(p('All individual staves were found, but <b>six of the eight tunes had the singing parts grouped incorrectly</b>. A staff is one set of five lines; a system is the group of staves that should sound together. Finding the lines is not enough.'))
story.append(box('<b>These are selected challenge cases.</b> Six out of ten is a result for those ten damaged heads, not a 60% accuracy rating for Southern Harmony. Some shape and damage combinations are still missing from the sample.', warm=True))

page(7, 'The biggest problems and a way forward')
story.append(p('The next gains need to address several different failure points. The actions below are proposed next work; their benefits have not yet been measured.'))
story.append(table([
    ['Problem', 'How we can tackle it'],
    ['Parts grouped wrongly', 'First repair how staves are grouped into music systems. Test three-part and four-part pages separately, including layouts that broke the current rules.'],
    ['Real notes missed or called rests', 'Use reviewed failures as labeled examples. Test better local searches and possible training on four shape scans, including genuine rests and damaged heads.'],
    ['Dirt and duplicate notes survive', 'Compare nearby candidates and source ink before writing extra notes. Show uncertain cases for review. A surviving candidate is not automatically a recovery.'],
    ['Rhythm can drift across voices', 'Check bar boundaries, dots, stems and beams together. Preserve visible notes and flag conflicts rather than dropping notes to make a bar fit.'],
    ['The score comparison is imperfect', 'Proofread a small reference set from the same historical scans. Check pitch, length, voice and timing, then test complete tunes from unseen pages.'],
], [144,356], header=True))
heading('Recommended next step', 'Focus the next development round on <b>system grouping and duplicate handling</b>, using the failures already observed. Then freeze the revised code and test it on newly selected pages before making another change. Keep the experimental rhythm stage optional. [8]')
heading('Alternative', 'Keep the code fixed and expand the independently reviewed examples, especially missing shape and damage combinations. This would strengthen the evidence before investing in a larger model change.')

page(8, 'How to judge the results')
story.append(box('<b>The next useful milestone:</b> measure how many complete tunes need correction and how long proofreading takes. That would tell us more about practical readiness than a successful export alone.'))
story.append(Spacer(1,6))
heading('A lower comparison score is encouraging', 'The main score counts edits needed to make the output\'s pitches and note lengths agree with reference MusicXML. It can count missing notes, extra notes and changed values. Lower is better. A separate timing score checks exact note events and when they occur.')
heading('Agreement is not the same as historical accuracy', 'Most references are from a 2025 edition while the scans are older. A real edition difference can raise the disagreement score even when the scan was read correctly. These tests also do not fully score lyrics, shape meaning, ties, beams or repeats. We therefore cannot turn the results into a trustworthy percentage of perfectly transcribed songs.')
heading('A bar that adds up can still be wrong', 'The dot/head development checkpoint still had 80 unresolved groups of parallel bars out of 2,104. Fourteen reflect Ninety-Third Psalm\'s printed meter conflict. The chosen policy preserves the printed 3/4 and flags the unusual bars. Equal bar lengths across parts do not certify the notes. [6]')
story.append(p('Evidence behind this overview', 'heading'))
story.append(p('The numbered links open the project records used here. The plain-language conclusions above distinguish demonstrated results from proposed next work.', 'small'))

MAIN='https://github.com/marktgodfrey/sacredharp_omr/blob/4fbe781313add2c13ee86151c736282328cdd7bb/'
FORK='https://github.com/marktgodfrey/copisteria/blob/8db7c33747203e466203b61e1aa59a20f8f991bc/'
SOURCES=[
    ('Copisteria engine and outputs', FORK+'README.md', 'copisteria/README.md'),
    ('Apple prototype and shape output', FORK+'docs/IOS_EXPERIMENT.md', 'copisteria/docs/IOS_EXPERIMENT.md'),
    ('Staff masking and local recovery history', MAIN+'diagnostics/rhythm-resolution/HANDOFF_HISTORY_2026-11-26.md', 'benchmarks/sacred-harp-1911/experiments/local-recovery/final-0996d2a689dc/REPORT.md'),
    ('Eighteen reviewed head recoveries history', MAIN+'diagnostics/rhythm-resolution/HANDOFF_HISTORY_2026-11-26.md', 'benchmarks/sacred-harp-1911/experiments/missing-proposals/final-d190393b6a83/REPORT.md'),
    ('Source grouping and rhythm repair history', MAIN+'diagnostics/rhythm-resolution/HANDOFF_HISTORY_2026-11-26.md', 'benchmarks/sacred-harp-1911/experiments/proposal-rhythm/final-0318d4f06bb9/REPORT.md'),
    ('Later dot and rhythm checkpoint', MAIN+'benchmarks/sacred-harp-1911/experiments/rhythm-resolution/dot-head-evidence-20261126-b6512a5f402d/REPORT.md', 'benchmarks/sacred-harp-1911/experiments/rhythm-resolution/dot-head-evidence-20261126-b6512a5f402d/REPORT.md'),
    ('Cross-printing results and safeguards', MAIN+'HANDOFF.md', 'HANDOFF.md'),
    ('Severe four shape test and failures', MAIN+'benchmarks/crossbook-frozen-rules/runs/severe-four-shape-holdout-20261127/REPORT.md', 'benchmarks/crossbook-frozen-rules/runs/severe-four-shape-holdout-20261127/REPORT.md'),
]
for i,(label,url,_) in enumerate(SOURCES,1):
    story.append(p(f'[{i}] <link href="{escape(url)}" color="#087A78">{label}</link>', 'small'))

def footer(c, doc):
    c.setTitle('Reading four shape tunebooks with OMR')
    c.setAuthor('Sacred Harp OMR project')
    c.setSubject('Plain language project overview and readiness assessment')
    c.setFont('Body',9)
    c.setFillColor(MUTED)
    c.drawString(56,29,'Sacred Harp OMR  |  27 November 2026')
    c.drawRightString(556,29,f'{doc.page} / {PAGE_COUNT}')

doc=SimpleDocTemplate(str(PDF), pagesize=(612,792), leftMargin=56, rightMargin=56, topMargin=43, bottomMargin=49)
doc.build(story, onFirstPage=footer, onLaterPages=footer)
reader=PdfReader(PDF)
assert len(reader.pages)==PAGE_COUNT, f'Expected {PAGE_COUNT} pages, found {len(reader.pages)}'
for i,page_obj in enumerate(reader.pages,1):
    text=page_obj.extract_text()
    assert f'{i} / {PAGE_COUNT}' in text
    assert len(text)>500
record={
    'pdf':PDF.name, 'pages':len(reader.pages),
    'pdf_sha256':hashlib.sha256(PDF.read_bytes()).hexdigest(),
    'source_sha256':{path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for _,_,path in SOURCES},
    'chart_counts':[5931,5686,5021,3650,3312],
    'chart_scope':'120 development/diagnostic songs; earlier research baseline to b651, not c291',
    'accuracy_page':4,
    'accuracy_data':ACCURACY,
    'accuracy_data_sha256':hashlib.sha256((OUT/'overview-accuracy-data.json').read_bytes()).hexdigest(),
    'visual_review':'pending',
}
(OUT/'overview-verification.json').write_text(json.dumps(record,indent=2)+'\n')
print(PDF)
