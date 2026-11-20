"""Optional bounded protocol adapters; no memory lookup, grants or recovery."""
import argparse
import json
import socket
import struct


def receive(sock,n):
    data=b''
    while len(data)<n:
        chunk=sock.recv(n-len(data))
        if not chunk:raise ValueError('incomplete-kafka-response')
        data+=chunk
    return data


def request(host,port,api,version,payload,timeout):
    correlation=534252
    body=struct.pack('>hhih',api,version,correlation,9)+b'knowledge'+payload
    with socket.create_connection((host,port),timeout=timeout) as sock:
        sock.settimeout(timeout);sock.sendall(struct.pack('>i',len(body))+body)
        size=struct.unpack('>i',receive(sock,4))[0]
        if not 4<=size<=1048576:raise ValueError('invalid-kafka-response-size')
        result=receive(sock,size)
    if struct.unpack('>i',result[:4])[0]!=correlation:raise ValueError('kafka-correlation-mismatch')
    return result[4:]


def kafka(host,port,timeout=2):
    versions=request(host,port,18,0,b'',timeout)
    if len(versions)<6:raise ValueError('invalid-api-versions')
    error,count=struct.unpack('>hi',versions[:6])
    if error or not 1<=count<=1000 or len(versions)!=6+6*count:raise ValueError('kafka-api-versions-not-ready')
    metadata=request(host,port,3,1,struct.pack('>i',0),timeout)
    offset=0
    def number(fmt):
        nonlocal offset
        size=struct.calcsize(fmt);value=struct.unpack_from(fmt,metadata,offset)[0];offset+=size;return value
    def string(nullable=False):
        nonlocal offset
        n=number('>h')
        if nullable and n==-1:return None
        if n<0 or offset+n>len(metadata):raise ValueError('invalid-kafka-string')
        value=metadata[offset:offset+n].decode('utf-8');offset+=n;return value
    count=number('>i')
    if not 1<=count<=100:raise ValueError('kafka-no-brokers')
    brokers=[]
    for _ in range(count):
        identifier=number('>i');address=string();endpoint=number('>i');string(True)
        brokers.append((identifier,address,endpoint))
    controller=number('>i');topics=number('>i')
    if controller not in [b[0] for b in brokers] or topics!=0 or offset!=len(metadata):raise ValueError('kafka-metadata-not-ready')
    # Advertised endpoints must also work from the test execution environment.
    for _,address,endpoint in brokers:
        response=request(address,endpoint,18,0,b'',timeout)
        if len(response)<6 or struct.unpack('>h',response[:2])[0]:raise ValueError('kafka-advertised-endpoint-not-ready')
    return {'ready':True,'protocol':'Kafka ApiVersions v0 + Metadata v1','brokers':len(brokers),'controller':controller}


def main():
    p=argparse.ArgumentParser();p.add_argument('kind',choices=['kafka']);p.add_argument('--host',required=True);p.add_argument('--port',type=int,required=True);p.add_argument('--timeout',type=float,default=2);a=p.parse_args()
    try:
        if not 0<a.timeout<=10 or not 0<a.port<65536:raise ValueError('invalid-probe-bound')
        result=kafka(a.host,a.port,a.timeout)
    except (OSError,ValueError,UnicodeError,struct.error) as error:
        result={'ready':False,'error':type(error).__name__}
    print(json.dumps(result));return 0 if result['ready'] else 1


if __name__=='__main__':raise SystemExit(main())
