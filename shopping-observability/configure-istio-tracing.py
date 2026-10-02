"""Merge the Git tracing fragment into the existing unmanaged Istio control plane.

Run through the approved trace runner. Existing discovery, trust, metrics and
meshNetworks config are preserved. This does not reinstall Istio or restart it.
"""
import json
from pathlib import Path
import subprocess
import yaml

fragment=yaml.safe_load((Path(__file__).parent/'helmchart/files/istio-tracing-provider.yaml').read_text())
k=['kubectl','--context','k3d-lab-k8s','-n','istio-system']
cm=json.loads(subprocess.check_output(k+['get','configmap','istio','-o','json'],text=True))
mesh=yaml.safe_load(cm['data']['mesh'])
assert mesh.get('rootNamespace')=='istio-system'
existing=mesh.setdefault('extensionProviders',[])
for provider in fragment['extensionProviders']:
    for entry in existing:
        if entry['name']==provider['name']:
            assert entry==provider, 'Conflicting existing provider: review before overwriting.'
            break
    else:
        existing.append(provider)
mesh['enableTracing']=True
patch={'metadata':{'resourceVersion':cm['metadata']['resourceVersion']},'data':{'mesh':yaml.safe_dump(mesh,sort_keys=False)}}
subprocess.run(k+['patch','configmap','istio','--type=merge','--patch-file=/dev/stdin'],input=json.dumps(patch),text=True,check=True)
print('Merged shopping-otel provider; preserved existing mesh settings and meshNetworks. No reinstall/restart.')
