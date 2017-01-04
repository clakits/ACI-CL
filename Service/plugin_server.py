from flask import Flask, render_template, redirect, url_for, request, flash, g, jsonify
import cobra.mit.access
import cobra.mit.session
import cobra.mit.request
from cobra.mit.access import MoDirectory
from cobra.mit.session import CertSession
from cobra.mit.session import LoginSession
from cobra.model.pol import Uni as PolUni
from cobra.model.aaa import UserEp as AaaUserEp
from cobra.model.aaa import AppUser as AaaAppUser
from cobra.model.aaa import UserCert as AaaUserCert
from cobra.internal.codec.jsoncodec import toJSONStr, fromJSONStr
from cobra.internal.codec.xmlcodec import _toXMLStr, fromXMLStr
import json

from cobra.mit.naming import Dn
from cobra.mit.request import DnQuery
from cobra.mit.request import ClassQuery
from cobra.mit.request import TraceQuery

import re
import time

import json
import datetime
import traceback

import requests.packages.urllib3
requests.packages.urllib3.disable_warnings()

app = Flask(__name__)

def log(s):
    with open("/home/app/log/EpgInfo.log", "a+") as log_file:
        log_file.write(" -- {0}\n".format(s))

    return

def createCertSession():
    log('createCertSession()')
    certUser = 'Cisco_EpgInfo'
    pKeyFile = '/home/app/credentials/plugin.key'
    
    polUni = PolUni('')
    aaaUserEp = AaaUserEp(polUni)
    aaaAppUser = AaaAppUser(aaaUserEp, certUser)

    aaaUserCert = AaaUserCert(aaaAppUser, certUser)

    with open(pKeyFile, "r") as file:
        pKey = file.read()

    apicUrl = 'https://172.17.0.1/'
    session = CertSession(apicUrl, aaaUserCert.dn, pKey, secure=False)
    return session

def respFormatJsonMos(mos, totalCount):
    jsonStr = '{"totalCount": "%s", "imdata": [' % totalCount
    first = True
    for mo in mos:
        if not first:
            jsonStr += ','
        else:
            first = False
        jsonStr += toJSONStr(mo, includeAllProps=True)
    jsonStr += ']}'
    jsonDict = json.loads(jsonStr)
    print json.dumps(jsonDict['imdata'])
    return json.dumps(jsonDict['imdata'])

def tDnToPath(tDn):

    #uni/tn-Tenant2phy/ap-appProfile/epg-EPG_1021/cep-00:50:56:AC:B6:92/rscEpToPathEp-[topology/pod-1/pathgrp-[10.201.32.32]]

    #uni/tn-Tenant1vir/l2out-L2Out_BD_2012/instP-L2Out_BD_2012/cep-FC:99:47:53:9C:69/rscEpToPathEp-[topology/pod-1/protpaths-103-104/pathep-[policyGroupforL2OUT]]
    
    #uni/tn-TA-3Tier/ap-TA-3Tier/epg-unknown-3/cep-00:50:56:AC:EE:E0/rscEpToPathEp-[topology/pod-1/protpaths-101-102/pathep-[policyGroupforTA]]
    #uni/tn-Tenant4_OTV/ap-OTV_Transit_AP/epg-EPG2/cep-F8:66:F2:11:AA:C3/rscEpToPathEp-[topology/pod-1/paths-102/pathep-[eth1/42]]

    try:
        m = re.search('tn-(.+)/ap-(.+)/epg-(.+)/cep-(.+)/rscEpToPathEp-\[topology/(.+)/(paths|protpaths)-(.+)/pathep-\[(.+)]]', str(tDn))
        n = re.search('tn-(.+)/ap-(.+)/epg-(.+)/cep-(.+)/rscEpToPathEp-\[topology/(.+)/(pathgrp)-\[(.+)]]', str(tDn))
        o = re.search('tn-(.+)/l2out-(.+)/instP-(.+)/cep-(.+)/rscEpToPathEp-\[topology/(.+)/(paths|protpaths)-(.+)/pathep-\[(.+)]]', str(tDn))
    except Exception as e:
        print 'ERROR:', e

    if m: return m.group(1),m.group(2),m.group(3),m.group(4),m.group(5),m.group(7),m.group(8)
    elif n: return n.group(1),n.group(2),n.group(3),n.group(4),n.group(5),n.group(7),'na'
    elif o: return o.group(1),o.group(2),o.group(3),o.group(4),o.group(5),o.group(7),o.group(8)
    else: return 'na','na','na','na','na','na','na'

def tDnToBdCtx(tDn,type):
    m=None
    try: m = re.search('tn-(.+)/%s-(.+)' % type, str(tDn))  
    except Exception as e: print 'ERROR:', e

    if m: return m.group(2)
    else: return 'na'

def getAncestorDnStrFromDnString(md, input, level):

    fvAEPg_dnStr = str(Dn.fromString(input).getAncestor(level))

    tq = TraceQuery(fvAEPg_dnStr, 'fvBD')
    tq.subtree = 'children'
    fvBD = md.query(tq)[0]

    bd=tDnToBdCtx(str(fvBD.dn),'BD')
    ctx=tDnToBdCtx((fvBD.rsctx._childObjects[None].tDn),'ctx')
    if bd and ctx: return bd,ctx
    else: return 'na','na'

class endPointEPG(object):
    
    def __init__(self):
        self.endPoint = []

    def addEndPoint(self,endPoint):
        self.endPoint.append(endPoint)

    def returnEndPoint(self):
        return self.endPoint

def printEndPoints(endPointDict):
    for epg in endPointDict:
        print epg, endPointDict[epg].returnEndPoint()


@app.route('/getEpg.json')
def home():
    with open("/home/app/data/logs.txt", "a") as log_file:
        log_file.write("==================================================" + "\n")
        log_file.write("Received API Request from Client. Sending Response" + "\n")
        log_file.write("==================================================" + "\n")

    reply = None
    try:
        apicUrl = 'https://172.17.0.1/'
        loginSession = createCertSession()
    

        #loginSession = cobra.mit.session.LoginSession('https://10.22.47.171', 'admin', 'ins3965!')
        moDir = MoDirectory(loginSession)
        moDir.login()

        tableList = []
        #row =  ('TN', 'AP/L2OUT', 'EPG/InstP', 'CEP', 'IP', 'Type', 'PATH', 'PORT', 'POD', 'ENCAP', 'BD:CTX')
        #tableList.append(row)
        try:
            row ={}
            q = ClassQuery('fvCEp')
            q.subtree = 'children'
            tenantMo = moDir.query(q)
        except cobra.mit.request.QueryError as e:
            log('Reason: ' + e.reason)
            log('Error: ' + e.error)
            log('HTTP code: ' + e.httpCode)
            log(traceback.format_exc())

        data = {}

        for mo in tenantMo:
            for child in mo.rscEpToPathEp:
                #print child.dn
                ip = mo.ip

                tn, ap, epg, cep, varPod, varStrPath, varStrPort = tDnToPath(child.dn)
                if 'protpaths' in child.tDn: portType = 'vPC'
                elif 'paths' in child.tDn and 'eth' in child.tDn: portType = '-'
                else: portType = 'PC'
                encap = (mo.encap).split('-')[1]

                #if args.macSearch: bd,ctx = getAncestorDnStrFromDnString(md, str(mo.dn), 1)
                #else: bd='-'; ctx='-'
                bd='-'; ctx='-'

                #row = (tn,ap,epg,cep,mo.ip,portType,varStrPath,varStrPort,varPod,encap,'%s:%s' %(bd,ctx))
                row = {
                    "tn": tn,
                    "ap/l2out":ap,
                    "epg":epg,
                    "cep":cep,
                    "ip":mo.ip,
                    "type":portType,
                    "path":varStrPath,
                    "port":varStrPort,
                    "pod":varPod,
                    "encap":encap,
                    "bd":"-:-"
                }
                tableList.append(row)

                #data[child.tDn]= row
        moDir.logout()
        #print json.dumps(data)
        #return render_template('home.html', table=tableList)
        #return respFormatJsonMos(data, len(data))
        log(tableList)
        reply = jsonify({'results': tableList})

    except Exception as e:
        log(traceback.format_exc())

    return reply


@app.route('/hello')
def hello_world():
    return 'Hello Version 1.0'

@app.route('/getTenant.json')
def get_tenant():
    with open("/home/app/data/logs.txt", "a") as log_file:
        log_file.write("==================================================" + "\n")
        log_file.write("Received API Request from Client. Sending Response" + "\n")
        log_file.write("==================================================" + "\n")

    apicUrl = 'https://172.17.0.1/'
    loginSession = createCertSession()
    #loginSession = LoginSession(apicUrl, 'admin', 'ins3965!')
    #loginSession = cobra.mit.session.LoginSession('https://10.22.47.171', 'admin', 'ins3965!')
    moDir = MoDirectory(loginSession)
    moDir.login()
    tenantMo = moDir.lookupByClass('fvTenant');
    moDir.logout()
    #print json.dumps(tenantMo)
    return respFormatJsonMos(tenantMo, tenantMo.totalCount)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
