"""Owner-approved capability factories; user parameters are data, never argv.

The memory engine remains generic. This optional Docker/Kafka adapter materializes
one bounded existing-resource procedure from explicitly supplied configuration or
user details. Merely defining a template does not permit its execution.
"""
from pathlib import Path
import re
from .util import require,digest


FIELDS={'id','kind','procedure_id','python','docker','defaults','deadline','interval','attempts','check_timeout','probe_timeout'}


def validate(template):
    require(isinstance(template,dict) and set(template)==FIELDS,'invalid-procedure-template')
    require(template['kind']=='docker-kafka-existing','unsupported-procedure-template')
    require(all(isinstance(template[k],str) and template[k].isidentifier() for k in ('id','procedure_id')),'invalid-template-id')
    require(all(isinstance(template[k],str) and Path(template[k]).is_absolute() for k in ('python','docker')),'template-tool-must-be-absolute')
    require(type(template['deadline']) is int and 1<=template['deadline']<=120 and
        type(template['check_timeout']) is int and 1<=template['check_timeout']<=60 and
        type(template['probe_timeout']) is int and 1<=template['probe_timeout']<=10 and
        type(template['attempts']) is int and template['attempts'] in (0,1) and
        type(template['interval']) in (int,float) and .05<=template['interval']<=10,'invalid-template-bounds')
    parameters(template['defaults'],complete=False)
    return template


def parameters(value,complete=True):
    require(isinstance(value,dict) and set(value)<={'container','host','port'},'invalid-template-parameters')
    if complete:require(set(value)=={'container','host','port'},'template-binding-incomplete')
    if 'container' in value:require(isinstance(value['container'],str) and re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}',value['container']),'invalid-container-binding')
    if 'host' in value:require(value['host'] in ('127.0.0.1','localhost','::1'),'template-requires-loopback-readiness')
    if 'port' in value:require(type(value['port']) is int and 1<=value['port']<=65535,'invalid-template-port')
    return value


def materialize(template,values):
    validate(template);parameters(values,complete=False)
    bound={**template['defaults'],**values};parameters(bound)
    procedure={'id':template['procedure_id'],
        'check':{'argv':[template['python'],'-I','-m','knowledge.probes','kafka','--host',bound['host'],'--port',str(bound['port']),'--timeout',str(template['probe_timeout'])],
                 'timeout':template['check_timeout']},
        'docker':{'executable':template['docker'],'container':bound['container']},
        'attempts':template['attempts'],'deadline':template['deadline'],'interval':template['interval']}
    return {'adapter':'dependency','procedure':procedure,'capability':{'template':template['id'],'parameters':bound}}


def describe(template):
    validate(template)
    return {'adapter':'dependency','procedure_id':template['procedure_id'],'template':template['id'],
        'parameter_schema':{'container':'exact existing Docker container name','host':'loopback hostname','port':'integer 1..65535'},
        'configured_parameters':template['defaults'],'missing_parameters':sorted({'container','host','port'}-set(template['defaults'])),
        'behavior':'check Kafka protocol from test environment; start only this stopped existing resource once if explicitly authorized; bounded readiness wait'}


def permitted(policy,behavior):
    procedure=behavior['procedure']
    if any(digest(p)==digest(procedure) for p in policy.get('allowed_procedures',[])):return True
    cap=behavior.get('capability')
    if not isinstance(cap,dict) or cap.get('template') not in policy.get('allowed_templates',[]):return False
    template=next((t for t in policy.get('procedure_templates',[]) if t['id']==cap['template']),None)
    if template is None:return False
    expected=materialize(template,cap['parameters'])
    return digest(expected)==digest(behavior)
