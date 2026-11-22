"""Offline independent audit of the fixed external graph and mapping."""
import csv, heapq, json, math, statistics, sys, xml.etree.ElementTree as ET
from pathlib import Path
from prepare_E import (APP_SHA, GRAPH_SHA, HOT_SHA, BBOX, OSM_DATE, FILTER, NAMESPACE, assign, bounds, registry, d2, sha, require)

ROOT = Path(__file__).resolve().parent
UM = ROOT/'inputs_um'
def rows(p):
    with open(p, newline='', encoding='utf-8-sig') as f: return list(csv.DictReader(f))

def graph(p):
    root=ET.parse(p).getroot(); keys={e.attrib['id']:e.attrib['attr.name'] for e in root.findall('g:key',NAMESPACE)}
    def data(e): return {keys[x.attrib['key']]:x.text for x in e.findall('g:data',NAMESPACE)}
    nodes={int(e.attrib['id']):(float(data(e)['x']),float(data(e)['y'])) for e in root.findall('.//g:node',NAMESPACE)}
    adj={n:{} for n in nodes}
    for e in root.findall('.//g:edge',NAMESPACE):
        a,b=int(e.attrib['source']),int(e.attrib['target']); w=float(data(e)['length'])
        require(math.isfinite(w) and w>0,'Invalid road edge')
        adj[a][b]=min(adj[a].get(b,math.inf),w); adj[b][a]=min(adj[b].get(a,math.inf),w)
    def distance(n):
        d={n:0.}; q=[(0.,n)]
        while q:
            v,i=heapq.heappop(q)
            if v!=d[i]:continue
            for j,w in adj[i].items():
                t=v+w
                if t<d.get(j,math.inf):d[j]=t;heapq.heappush(q,(t,j))
        return d
    require(len(distance(next(iter(nodes))))==len(nodes),'Disconnected graph')
    return nodes,distance

def audit(paths):
    a,g,h=paths
    require([sha(p) for p in paths]==[APP_SHA,GRAPH_SHA,HOT_SHA],'Frozen source/inputs differ')
    m=json.loads((UM/'network_manifest.json').read_text())
    require(m['bbox_wsen']==list(BBOX) and m['osm_date_utc']==OSM_DATE and m['overpass_filter']==FILTER,'Wrong network query')
    require([m[k] for k in ('source_app_sha256','source_graph_sha256','source_hotspots_sha256')]==[APP_SHA,GRAPH_SHA,HOT_SHA],'Wrong provenance')
    require(set(m['hashes'])=={'utp_graph.graphml','hotspot_locations.csv','hotspot_mapping.csv','parking_mapping.csv','parking_registry.json'},'Unexpected manifest files')
    require(all(sha(UM/k)==v for k,v in m['hashes'].items()),'UM file hash mismatch')
    src,ds=graph(g); target,dt=graph(UM/'utp_graph.graphml')
    require(len(src)==474 and len(target)==5018,'Wrong node count')
    require(all(BBOX[0]-1e-7<=x<=BBOX[2]+1e-7 and BBOX[1]-1e-7<=y<=BBOX[3]+1e-7 for x,y in target.values()),'Node outside frozen bbox')
    hot=rows(h); new=rows(UM/'hotspot_locations.csv'); reg=registry(a)
    mapping,ha=assign({int(r['node']):src[int(r['node'])] for r in hot},target,bounds(src.values()),bounds(target.values()))
    parks,pa=assign({r['parking_id']:(r['lon'],r['lat']) for r in reg},target,bounds(src.values()),bounds(target.values()))
    require(len(hot)==len(new)==87 and len(mapping)==len(set(mapping.values()))==74 and len(parks)==len(set(parks.values()))==21,'Mapping cardinality mismatch')
    for filename,expected in [('hotspot_mapping.csv',ha),('parking_mapping.csv',pa)]:
        got=rows(UM/filename);require(len(got)==len(expected),'Mapping count mismatch')
        for x,y in zip(got,expected):
            require(str(y['source_id'])==x['source_id'] and int(x['target_node'])==y['target_node'],'Mapping identity mismatch')
            require(all(math.isclose(float(x[k]),y[k],rel_tol=1e-11,abs_tol=1e-9) for k in ('target_lon','target_lat','ideal_lon','ideal_lat','snap_approx_m')),'Mapping coordinate mismatch')
    for x,y in zip(hot,new):
        n=mapping[int(x['node'])];require(int(y['node'])==n and (float(y['lon']),float(y['lat']))==target[n],'Hotspot geometry mismatch')
        require({k:v for k,v in x.items() if k not in ('node','lon','lat')}=={k:v for k,v in y.items() if k not in ('node','lon','lat')},'Demand weights or order changed')
    expected=[dict(parking_id=r['parking_id'],lat=target[parks[r['parking_id']]][1],lon=target[parks[r['parking_id']]][0]) for r in reg]
    require(json.loads((UM/'parking_registry.json').read_text())==expected,'Registry mismatch')
    active=sorted({int(r['node']) for r in hot if r['demand_weight'] and float(r['demand_weight'])>0}); ids=['P02','P08','P16']; rp={r['parking_id']:r for r in reg}
    oldparks={k:min(src,key=lambda n:(d2(src[n],(rp[k]['lon'],rp[k]['lat'])),n)) for k in ids}
    def stats(xs):
        s=sorted(xs); return dict(min=s[0],p10=s[round(.1*(len(s)-1))],median=statistics.median(s),p90=s[round(.9*(len(s)-1))],max=s[-1])
    for name,fn,ns,dp in [('UTP',ds,active,list(oldparks.values())),('UM_district',dt,[mapping[n] for n in active],[parks[k] for k in ids])]:
        distances={n:fn(n) for n in set(ns)|set(dp)}
        for metric,values in [('OD_shortest_m',[distances[i][j] for i in ns for j in ns if i!=j]),('closest_depot_m',[min(distances[d][i] for d in dp) for i in ns])]:
            require(all(math.isclose(v,m['metrics'][name][metric][k],rel_tol=1e-9,abs_tol=1e-6) for k,v in stats(values).items()),f'{name} {metric}: metric mismatch')
    return {'manifest':m,'um_to_utp':{v:k for k,v in mapping.items()},'depots':{'UTP':oldparks,'UM_district':{k:parks[k] for k in ids}}}

if __name__=='__main__':
    from ugvkit.common import repo_paths
    paths=tuple(map(Path,sys.argv[1:])) if len(sys.argv)==4 else repo_paths('~/ugv-benchmark-public')
    result=audit(paths);print('PASS: source and network hashes, graph connectivity, 87 rows, 74 unique hotspot mappings, 21 depot mappings, shortest-path metrics.');print(result['depots'])
