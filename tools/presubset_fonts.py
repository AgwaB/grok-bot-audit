# Build-time helper (not shipped as runtime code): subset OFL fonts to Latin + KS X 1001 Hangul and rename.
import sys, os
from fontTools import subset
from fontTools.ttLib import TTFont
import argparse
ap = argparse.ArgumentParser(description='Subset + rename the original OFL fonts into assets/fonts (maintainers only).')
ap.add_argument('src', help='folder with the original TTFs'); a = ap.parse_args()
SRC = a.src; DST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'fonts')
latin = ''.join(map(chr, range(0x20, 0x7f))) + ''.join(map(chr, range(0xa0, 0x180))) + '“”‘’…·→←–—■□✓•€₩'
hangul = ''.join(c for c in map(chr, range(0xac00, 0xd7a4)) if len(c.encode('euc-kr', 'ignore')) == 2)
jamo = ''.join(map(chr, range(0x3131, 0x318f)))
cjkp = '「」『』《》〈〉【】、。・～'
JOBS = [('IBMPlexSans-Regular.ttf', 'Report Sans', 400, latin), ('IBMPlexSans-SemiBold.ttf', 'Report Sans', 600, latin),
        ('Newsreader-Regular.ttf', 'Report Serif', 400, latin),
        ('IBMPlexSansKR-Regular.ttf', 'Report Sans KR', 400, latin + hangul + jamo + cjkp),
        ('IBMPlexSansKR-SemiBold.ttf', 'Report Sans KR', 600, latin + hangul + jamo + cjkp),
        ('GowunBatang-Regular.ttf', 'Report Serif KR', 400, latin + hangul + jamo + cjkp)]
for fn, fam, wt, chars in JOBS:
    opt = subset.Options(); opt.name_IDs = ['*']; opt.name_languages = ['*']; opt.layout_features = ['*']; opt.notdef_outline = True
    f = TTFont(os.path.join(SRC, fn)); s = subset.Subsetter(opt); s.populate(text=chars); s.subset(f)
    style = 'SemiBold' if wt == 600 else 'Regular'
    for rec in f['name'].names:
        if rec.nameID in (1, 16, 21): rec.string = fam
        elif rec.nameID == 4: rec.string = fam + ('' if wt == 400 else ' SemiBold')
        elif rec.nameID in (2, 17, 22): rec.string = style
        elif rec.nameID in (3, 6, 20): rec.string = fam.replace(' ', '') + '-' + style
    out = os.path.join(DST, fam.replace(' ', '') + '-' + style + '.ttf'); f.save(out)
    print(out, os.path.getsize(out) // 1024, 'KB')
