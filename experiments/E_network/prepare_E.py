#!/usr/bin/env python3
"""Acquire and fingerprint a fixed external network, without modifying the simulator.

Run in the existing UGV environment. No simulations are launched here.
"""
import argparse
import ast
import csv
import hashlib
import json
import math
import statistics
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone
import zipfile

APP_SHA='7b52bb550414469937da3098f91313b366137d43bd48b8465b840a97bffeb0a0'
GRAPH_SHA='ebd138a83763f11172e079f40457b371be7eebcd2e3aa018aeda13d9d70114f4'
HOT_SHA='6a55a275f2ac18ab383d2efcd67a31250602503a62fa3c5bf2f3f504ae0b979d'
BBOX=(101.642,3.108,101.670,3.134)  # west, south, east, north
OSM_DATE='2025-10-01T00:00:00Z'
FILTER='["highway"~"^(tertiary|residential|unclassified|living_street|service)$"]["area"!="yes"]["access"!="no"]["motor_vehicle"!="no"]'
NAMESPACE={'g':'http://graphml.graphdrawing.org/xmlns'}

def require(ok,msg):
    if not ok: raise ValueError(msg)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def source_paths(repo):
    repo=Path(repo).expanduser();a=repo/'src/frozen/app.py';g=repo/'inputs/utp_graph.graphml';h=repo/'inputs/hotspot_locations.csv'
    if not g.exists():g=repo/'inputs/utp_graph.graphml.xml'
    require([sha(x) for x in (a,g,h)]==[APP_SHA,GRAPH_SHA,HOT_SHA],'Frozen UTP input hash mismatch')
    return a,g,h

def reference_graph(p):
    root=ET.parse(p).getroot();key={x.attrib['id']:x.attrib['attr.name'] for x in root.findall('g:key',NAMESPACE)}
    nodes={}
    for n in root.findall('.//g:node',NAMESPACE):
        d={key[x.attrib['key']]:x.text for x in n.findall('g:data',NAMESPACE)};nodes[int(n.attrib['id'])]=(float(d['x']),float(d['y']))
    require(len(nodes)==474,'Unexpected original graph node count');return nodes

def registry(p):
    t=ast.parse(p.read_text());values=[ast.literal_eval(n.value) for n in t.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='PARKING_REGISTRY' for x in n.targets)]
    require(len(values)==1 and len(values[0])==21,'Unexpected parking registry');return values[0]

def bounds(coords):
    return min(x for x,y in coords),min(y for x,y in coords),max(x for x,y in coords),max(y for x,y in coords)

def transform(p,src,dst):
    x,y=p;a,b,c,d=src;e,f,g,h=dst;require(c>a and d>b,'Degenerate source bounds')
    return e+(x-a)/(c-a)*(g-e),f+(y-b)/(d-b)*(h-f)

def d2(p,q):
    return ((p[0]-q[0])*math.cos(math.radians((p[1]+q[1])/2)))**2+(p[1]-q[1])**2

def assign(points,target,source_box,target_box):
    """Fixed sorted greedy one-to-one assignment, no outcomes or demand tuning."""
    available=set(target);result={};report=[]
    require(len(available)>=len(points),'Not enough distinct target nodes')
    for k,p in sorted(points.items()):
        q=transform(p,source_box,target_box);best=min(available,key=lambda n:(d2(q,target[n]),n));available.remove(best)
        result[k]=best;report.append(dict(source_id=k,target_node=best,target_lon=target[best][0],target_lat=target[best][1],ideal_lon=q[0],ideal_lat=q[1],snap_approx_m=111195*math.sqrt(d2(q,target[best]))))
    return result,report

def write_csv(path,rows):
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def metrics(G,hot_nodes,depots,nx):
    values=[];closest=[]
    ds={n:nx.single_source_dijkstra_path_length(G,n,weight='length') for n in sorted(set(hot_nodes)|set(depots))}
    for i in hot_nodes:
        values.extend(ds[i][j] for j in hot_nodes if j!=i);closest.append(min(ds[d][i] for d in depots))
    def summarize(xs):
        s=sorted(xs);return {'min':s[0],'p10':s[round(.1*(len(s)-1))],'median':statistics.median(s),'p90':s[round(.9*(len(s)-1))],'max':s[-1]}
    return dict(nodes=G.number_of_nodes(),edges=G.number_of_edges(),network_km=sum(float(d['length']) for _,_,d in G.edges(data=True))/1000,OD_shortest_m=summarize(values),closest_depot_m=summarize(closest))

def prepare(repo,out):
    a,g,h=source_paths(repo);src=reference_graph(g);reg=registry(a);hot=list(csv.DictReader(h.open(encoding='utf-8-sig')))
    require(len(hot)==87 and len({int(r['node']) for r in hot})==74,'Original hotspot rows changed')
    import networkx as nx
    import osmnx as ox
    from shapely.geometry import box
    require(not out.exists() and not (out.parent/(out.name+'.zip')).exists(),'Output exists: refusing to overwrite. Upload the existing ZIP or select another output path.')
    out.parent.mkdir(parents=True,exist_ok=True)
    # Fixed historical snapshot; OSMnx HTTP cache is retained for reproducibility.
    ox.settings.use_cache=True;ox.settings.cache_folder=out.parent/'osm_cache_E';ox.settings.requests_timeout=180
    ox.settings.overpass_settings='[out:json][timeout:{timeout}][date:"'+OSM_DATE+'"]'
    print('Downloading historical OpenStreetMap network. No fleet simulations will run.',flush=True)
    raw=ox.graph.graph_from_polygon(box(*BBOX),network_type='drive_service',simplify=False,retain_all=True,truncate_by_edge=False,custom_filter=FILTER)
    U=ox.convert.to_undirected(raw)
    comp=max(nx.connected_components(U),key=lambda s:(len(s),-min(s)));U=U.subgraph(comp).copy();G=raw.subgraph(comp).copy()
    require(len(U)>=95 and nx.is_connected(U),'External network too small or disconnected; no automatic fallback')
    require(all(math.isfinite(float(d['length'])) and float(d['length'])>0 for _,_,d in U.edges(data=True)),'Invalid length')
    target={int(n):(float(d['x']),float(d['y'])) for n,d in U.nodes(data=True)}
    sb=bounds(src.values());tb=bounds(target.values())
    unique={int(r['node']):src[int(r['node'])] for r in hot};mapping,audit=assign(unique,target,sb,tb)
    parks,paudit=assign({r['parking_id']:(r['lon'],r['lat']) for r in reg},target,sb,tb)
    ext_hot=[dict(r,node=mapping[int(r['node'])],lon=target[mapping[int(r['node'])]][0],lat=target[mapping[int(r['node'])]][1]) for r in hot]
    ext_park=[dict(parking_id=r['parking_id'],lat=target[parks[r['parking_id']]][1],lon=target[parks[r['parking_id']]][0]) for r in reg]
    require(len({r['node'] for r in ext_hot})==74 and len(set(parks.values()))==21,'Mapping lost identities')
    # Source graph and target use the exact same undirected semantics as frozen app.py.
    old=ox.load_graphml(filepath=g);old=ox.convert.to_undirected(old) if old.is_directed() else old
    active=sorted({int(r['node']) for r in hot if r['demand_weight'] and float(r['demand_weight'])>0})
    dp=('P02','P08','P16');rp={r['parking_id']:r for r in reg}
    olddep=[min(src,key=lambda n:(d2(src[n],(rp[k]['lon'],rp[k]['lat'])),n)) for k in dp]
    m=dict(UTP=metrics(old,active,olddep,nx),UM_district=metrics(U,[mapping[n] for n in active],[parks[k] for k in dp],nx))
    temp=Path(tempfile.mkdtemp(prefix='E_inputs_',dir=out.parent))
    ox.save_graphml(G,filepath=temp/'utp_graph.graphml')
    check=ox.load_graphml(filepath=temp/'utp_graph.graphml');check=ox.convert.to_undirected(check)
    require(set(check)==set(U) and nx.is_connected(check),'Saved GraphML round-trip failed')
    write_csv(temp/'hotspot_locations.csv',ext_hot);write_csv(temp/'hotspot_mapping.csv',audit);write_csv(temp/'parking_mapping.csv',paudit)
    (temp/'parking_registry.json').write_text(json.dumps(ext_park,indent=2)+'\n')
    manifest=dict(network='Universiti Malaya district (synthetic service geography)',bbox_wsen=BBOX,osm_date_utc=OSM_DATE,overpass_filter=FILTER,osmnx_version=ox.__version__,networkx_version=nx.__version__,source_app_sha256=APP_SHA,source_graph_sha256=GRAPH_SHA,source_hotspots_sha256=HOT_SHA,downloaded_utc=datetime.now(timezone.utc).isoformat(),directed_osm_graph=True,simulation_assumption='undirected, flat, 22 km/h cap; no claim of legal accessibility or real demand',license='OpenStreetMap contributors, ODbL https://www.openstreetmap.org/copyright',metrics=m,hashes={p.name:sha(p) for p in sorted(temp.iterdir())},mapping_rule='normalized source graph coordinate bounds to external graph bounds; sorted one-to-one nearest nodes; source row order and weights unchanged; depot IDs unchanged')
    (temp/'network_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    out.mkdir();
    for p in temp.iterdir():p.rename(out/p.name)
    temp.rmdir()
    z=out.parent/(out.name+'.zip')
    with zipfile.ZipFile(z,'x',compression=zipfile.ZIP_DEFLATED) as f:
        for p in sorted(out.iterdir()):f.write(p,p.name)
    with zipfile.ZipFile(z) as f:require(f.testzip() is None,'ZIP validation failed')
    print(json.dumps(m,indent=2));print('E INPUTS VERIFIED:',z,flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--repo',default='~/ugv-benchmark-public');ap.add_argument('--out',default='~/Downloads/EXP_E_network_inputs');args=ap.parse_args()
    try:prepare(args.repo,Path(args.out).expanduser().resolve())
    except Exception as e:print('STOP:',e,file=sys.stderr);sys.exit(1)
