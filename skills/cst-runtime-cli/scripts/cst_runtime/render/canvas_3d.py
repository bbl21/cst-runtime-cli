from __future__ import annotations

import json
import math
from typing import Any


def render_3d_farfield(data: dict[str, Any], container_id: str = "ff3d") -> str:
    theta = data.get("ypositions", [])
    phi = data.get("xpositions", [])
    gain = data.get("data", [])
    if not theta or not phi or not gain:
        return '<div class="chart-panel"><p>\u65e0\u53ef\u7528\u7684\u8fdc\u573a\u6570\u636e\uff0c\u65e0\u6cd5\u6e32\u67d3 3D \u89c6\u56fe</p></div>'

    ny = len(theta)
    nx = len(phi)
    vertices: list[list[float]] = []
    faces: list[list[int]] = []
    values: list[float | None] = []
    raw_vals: list[float | None] = []
    for i in range(ny):
        for j in range(nx):
            g = gain[i][j] if i < len(gain) and j < len(gain[i]) else None
            raw_vals.append(float(g) if g is not None else None)
    valid_vals = [v for v in raw_vals if v is not None]
    val_min = min(valid_vals) if valid_vals else -40
    val_max = max(valid_vals) if valid_vals else 14
    val_rng = max(val_max - val_min, 1)
    max_radius = 0.0
    for i in range(ny):
        for j in range(nx):
            g = raw_vals[i * nx + j]
            if g is None:
                r = 0.1
                v = None
            else:
                r = (g - val_min) / val_rng * 4.5 + 0.3
                v = g
                max_radius = max(max_radius, r)
            th = math.radians(float(theta[i]))
            ph = math.radians(float(phi[j]))
            x = r * math.sin(th) * math.cos(ph)
            y = r * math.sin(th) * math.sin(ph)
            z = r * math.cos(th)
            vertices.append([x, y, z])
            values.append(v)
    for i in range(ny - 1):
        for j in range(nx - 1):
            a = i * nx + j
            b = a + 1
            c = a + nx
            d = c + 1
            va, vb, vc, vd = values[a], values[b], values[c], values[d]
            if va is not None and vb is not None and vc is not None:
                faces.append([a, b, c, (va + vb + vc) / 3])
            if vb is not None and vd is not None and vc is not None:
                faces.append([b, d, c, (vb + vd + vc) / 3])

    if not faces:
        return '<div class="chart-panel"><p>\u65e0\u6709\u6548\u7684\u8fdc\u573a\u7f51\u683c\u6570\u636e</p></div>'

    z_all = sorted(f[3] for f in faces)
    z_count = len(z_all)

    camera_dist = max(max_radius * 2.5, 6)
    initial_zoom = 1.0

    vertices_json = json.dumps(vertices, separators=(",", ":"))
    faces_json = json.dumps(faces, separators=(",", ":"))
    z_sorted_json = json.dumps(z_all, separators=(",", ":"))

    js = f'''<canvas id="{container_id}" style="width:100%;min-height:460px;display:block;border-radius:12px;background:#18181b;"></canvas>
<script>
(function(){{
var V={vertices_json},F={faces_json};
var Z={z_sorted_json},zCnt={z_count};
var camDist={camera_dist:.1f},maxR={max_radius:.2f};
var cnv=document.getElementById("{container_id}");
if(!cnv)return;
var ctx=cnv.getContext("2d");
if(!ctx)return;
var W=Math.max(cnv.clientWidth||800,400),H=Math.max(W*0.75,350);
var zoom={initial_zoom:.1f},cx=0,cy=0;
var M=[1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1];
var M0=M.slice();
var dragging=false,lastSx=0,lastSy=0;
var autoRotate=0,autoRAF=0;

function startAuto(){{if(!autoRotate){{autoRotate=1;cnv.__autoRAF=requestAnimationFrame(autoFrame);}}}}
function stopAuto(){{autoRotate=0;if(cnv.__autoRAF){{cancelAnimationFrame(cnv.__autoRAF);cnv.__autoRAF=0;}}}}
function autoFrame(){{if(autoRotate){{M=matMul(axisAngle(0,0,1,0.008),M);draw();cnv.__autoRAF=requestAnimationFrame(autoFrame);}}}}
function resetView(){{stopAuto();M=M0.slice();zoom={initial_zoom:.1f};draw();}}

function resize(){{W=Math.max(cnv.clientWidth||800,400);H=Math.max(W*0.75,350);cnv.width=W;cnv.height=H;draw();}}

function colorMap(v){{var lo=0,hi=zCnt-1,mid;while(lo<=hi){{mid=(lo+hi)>>1;if(Z[mid]<v)lo=mid+1;else hi=mid-1;}}var t=Math.max(0,lo)/Math.max(zCnt-1,1);
var stops=[0,0.16,0.33,0.5,0.66,0.83,1];
var rs=[5,0,0,0,255,255,255],gs=[5,100,200,255,220,120,255],bs=[30,200,255,0,0,0,255];
var seg=0;while(seg<6&&t>stops[seg+1])seg++;
var s=(t-stops[seg])/(stops[seg+1]-stops[seg]+0.0001);
var r=Math.round(rs[seg]+s*(rs[seg+1]-rs[seg]));}}
var g=Math.round(gs[seg]+s*(gs[seg+1]-gs[seg]));
var b=Math.round(bs[seg]+s*(bs[seg+1]-bs[seg]));
return"rgb("+r+","+g+","+b+")";}}

function matMulVec(m,v){{var x=v[0],y=v[1],z=v[2];
return[x*m[0]+y*m[4]+z*m[8]+m[12],x*m[1]+y*m[5]+z*m[9]+m[13],x*m[2]+y*m[6]+z*m[10]+m[14]];}}

function matMul(a,b){{var r=new Array(16);
for(var i=0;i<4;i++)for(var j=0;j<4;j++){{var s=0;for(var k=0;k<4;k++)s+=a[i+k*4]*b[k+j*4];r[i+j*4]=s;}}
return r;}}

function axisAngle(ax,ay,az,angle){{
var c=Math.cos(angle),s=Math.sin(angle),t=1-c;
var x=ax,y=ay,z=az;
return[t*x*x+c, t*x*y+s*z, t*x*z-s*y, 0,
       t*x*y-s*z, t*y*y+c, t*y*z+s*x, 0,
       t*x*z+s*y, t*y*z-s*x, t*z*z+c, 0,
       0, 0, 0, 1];}}

function mapToSphere(x,y){{
var r=Math.min(W,H)*0.5;
var sx=(x-W/2)/r, sy=-(y-H/2)/r;
var len=Math.sqrt(sx*sx+sy*sy);
if(len>1){{sx/=len;sy/=len;len=1;}}
var sz=Math.sqrt(Math.max(0,1-len*len));
return[sx,sy,sz];}}

function project(v){{var p=matMulVec(M,v);
var x=p[0],y=p[1],z=p[2];
var s=zoom*maxR/camDist;
return{{x:W/2+(x+cx)*s*W/(2*maxR),y:H/2-(y+cy)*s*W/(2*maxR),z:z}};}}

function draw(){{
cnv.width=W;cnv.height=H;
ctx.clearRect(0,0,W,H);
ctx.fillStyle="#18181b";ctx.fillRect(0,0,H);
var proj=F.map(function(f){{return{{p:[project(V[f[0]]),project(V[f[1]]),project(V[f[2]])],v:f[3]}};}});
proj.sort(function(a,b){{var az=a.p[0].z+a.p[1].z+a.p[2].z,bz=b.p[0].z+b.p[1].z+b.p[2].z;return az-bz;}});
for(var i=0;i<proj.length;i++){{var p=proj[i];
ctx.fillStyle=colorMap(p.v);
ctx.strokeStyle="rgba(255,255,255,0.1)";
ctx.beginPath();ctx.moveTo(p.p[0].x,p.p[0].y);ctx.lineTo(p.p[1].x,p.p[1].y);ctx.lineTo(p.p[2].x,p.p[2].y);ctx.closePath();
ctx.fill();ctx.stroke();}}
}}

cnv.addEventListener("mousedown",function(e){{stopAuto();dragging=true;var r=cnv.getBoundingClientRect();lastSx=e.clientX-r.left;lastSy=e.clientY-r.top;cnv.style.cursor="grabbing";}});
window.addEventListener("mouseup",function(){{dragging=false;cnv.style.cursor="grab";}});
window.addEventListener("mousemove",function(e){{
if(!dragging)return;
var r=cnv.getBoundingClientRect();
var sx=e.clientX-r.left,sy=e.clientY-r.top;
var p0=mapToSphere(lastSx,lastSy);
var p1=mapToSphere(sx,sy);
var axis=[p0[1]*p1[2]-p0[2]*p1[1],p0[2]*p1[0]-p0[0]*p1[2],p0[0]*p1[1]-p0[1]*p1[0]];
var len=Math.sqrt(axis[0]*axis[0]+axis[1]*axis[1]+axis[2]*axis[2]);
if(len>1e-6){{axis[0]/=len;axis[1]/=len;axis[2]/=len;var dot=p0[0]*p1[0]+p0[1]*p1[1]+p0[2]*p1[2];dot=Math.max(-1,Math.min(1,dot));M=matMul(axisAngle(axis[0],axis[1],axis[2],Math.acos(dot)),M);}}
lastSx=sx;lastSy=sy;
draw();
}});
cnv.addEventListener("wheel",function(e){{e.preventDefault();zoom*=e.deltaY>0?0.9:1.1;zoom=Math.max(0.15,Math.min(8,zoom));draw();}});
cnv.addEventListener("touchstart",function(e){{stopAuto();if(e.touches.length==1){{dragging=true;var r=cnv.getBoundingClientRect();lastSx=e.touches[0].clientX-r.left;lastSy=e.touches[0].clientY-r.top;}}}});
cnv.addEventListener("touchmove",function(e){{if(!dragging||e.touches.length!=1)return;var r=cnv.getBoundingClientRect();var sx=e.touches[0].clientX-r.left,sy=e.touches[0].clientY-r.top;var p0=mapToSphere(lastSx,lastSy),p1=mapToSphere(sx,sy);var axis=[p0[1]*p1[2]-p0[2]*p1[1],p0[2]*p1[0]-p0[0]*p1[2],p0[0]*p1[1]-p0[1]*p1[0]];var len=Math.sqrt(axis[0]*axis[0]+axis[1]*axis[1]+axis[2]*axis[2]);if(len>1e-6){{axis[0]/=len;axis[1]/=len;axis[2]/=len;var dot=p0[0]*p1[0]+p0[1]*p1[1]+p0[2]*p1[2];dot=Math.max(-1,Math.min(1,dot));M=matMul(axisAngle(axis[0],axis[1],axis[2],Math.acos(dot)),M);}}lastSx=sx;lastSy=sy;draw();}});
cnv.addEventListener("touchend",function(){{dragging=false;}});
window.addEventListener("resize",resize);
M=matMul(axisAngle(0,1,0,0.4),M);
M=matMul(axisAngle(1,0,0,-0.5),M);
M0=M.slice();
cnv.resetView=resetView;
cnv.startAuto=startAuto;
cnv.stopAuto=stopAuto;
cnv.style.cursor="grab";
resize();
}})();
</script>'''
    return js