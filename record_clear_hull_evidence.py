from pathlib import Path
p=Path('finalize_textured_preview.py');s=p.read_text();s=s.replace("        evidence['prop_hull_hits']=count","        prop_results=re.findall(r'Phase Runner prop hull probe \\d+: fraction=([0-9.]+) startSolid=(\\w+)',log)\n        if len(prop_results)!=count or any(float(f)>=1 or solid!='false' for f,solid in prop_results):raise ValueError('Prop hull contacts did not start in clear space')\n        evidence['prop_hull_clear_start_contacts_verified']=True\n        evidence['prop_hull_hits']=count")
p.write_text(s)
