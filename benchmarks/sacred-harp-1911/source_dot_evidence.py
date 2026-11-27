"""Source-only exclusions for repeat dots and diffuse low-contrast marks."""
import numpy as np
from proposal_rhythm_evidence import _components


def diffuse_dot_mark(image,box,staff):
    """Recognize a broad pale mark rather than assuming any missing dot is false.

    Compare contrast with this head's own printed ink and retain dark marks,
    compact marks, and inconclusive crops. All sizes are in staff spaces.
    """
    pixels=np.asarray(image);x0,y0,x1,y1=box;sp=staff.sp
    head=pixels[max(0,int(y0)):min(pixels.shape[0],int(y1)+1),max(0,int(x0)):min(pixels.shape[1],int(x1)+1)]
    a=max(0,int(x1+.08*sp));b=min(pixels.shape[1],int(x1+.82*sp)+1)
    top=max(0,int((y0+y1)/2-.72*sp));bottom=min(pixels.shape[0],int((y0+y1)/2+.72*sp)+1)
    crop=pixels[top:bottom,a:b]
    empty={'diffuse_non_dot_mark':False}
    if head.size==0 or crop.size==0:return empty
    paper=float(np.percentile(head,90));ink=float(np.percentile(head,10))
    if paper-ink<80:return empty
    mask=crop<np.clip(paper-40,130,205)
    half=max(1,int(round(.08*sp)))
    for j in range(5):
        yy=int(round(staff.y0+j*sp-top))
        if yy+half>=0 and yy-half<mask.shape[0]:
            mask[max(0,yy-half):min(mask.shape[0],yy+half+1),:]=False
    for area,left,upper,right,lower in _components(mask):
        w,h=(right-left)/sp,(lower-upper)/sp
        if area<.22*sp*sp or max(w,h)<.6 or max(w,h)>1.2:continue
        local=crop[upper:lower,left:right];foreground=mask[upper:lower,left:right]
        contrast=(paper-float(np.median(local[foreground])))/(paper-ink)
        if 0<contrast<.45:
            return {'diffuse_non_dot_mark':True,'box':[a+left,top+upper,a+right,top+lower],
                    'relative_ink_contrast':round(contrast,3),'area_staff_spaces2':round(area/(sp*sp),3)}
    return empty


def component_is_repeat(component,repeat,rd,sp):
    if not repeat:return False
    box=component['box'];cx=(box[0]+box[2])/2;cy=(box[1]+box[3])/2
    centers=[(p['cx'],p['cy']) for p in repeat.get('pixel_components',[])]
    centers += [(rd.layout.syms[i].cx,rd.layout.syms[i].cy) for i in repeat.get('glyph_ids',[])]
    return any(abs(cx-x)<.3*sp and abs(cy-y)<.3*sp for x,y in centers)
