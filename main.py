# Implementazione openflow di hop-by-hop routing
# usando la mappa della rete trovata con topology discovery
#
# Si richiede l'uso del topology discovery
# ryu-manager --observe-links
#

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import set_ev_cls, CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.ofproto import ofproto_v1_3
from ryu.topology import event, switches
from ryu.topology.api import get_all_switch, get_all_link, get_all_host
from ryu.lib.packet import packet, ethernet, ether_types, arp
import networkx as nx

class HopByHopSwitch(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    # tutti i pacchetti al controllore
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                [
                    parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                           ofproto.OFPCML_NO_BUFFER)
                ]
            )
        ]
        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=0,
            match = parser.OFPMatch(),
            instructions=inst
        )
        datapath.send_msg(mod)
    # trova switch destinazione e porta dello switch
    def find_destination_switch(self,destination_mac):
        for host in get_all_host(self):
            if host.mac == destination_mac:
                return (host.port.dpid, host.port.port_no)
        return (None,None)


    '''

    def find_next_hop_to_destination(self,source_id,destination_id):
        net = nx.DiGraph()
        for link in get_all_link(self):
            net.add_edge(link.src.dpid, link.dst.dpid, port=link.src.port_no)

        path = nx.shortest_path(
            net,
            source_id,
            destination_id
        )

        first_link = net[ path[0] ][ path[1] ]

        return first_link['port']
        '''
    def create_tree(self):
        net = nx.Graph()

        for link in get_all_link(self):
            #TODO: Delete duplicates
            #net.add_edge(1,2)
            #print(type(link))
            #print(link)
            if(net.has_edge(link.src.dpid, link.dst.dpid)==False):
                ports = {}
                ports[str(link.src.dpid)] = link.src.port_no;
                ports[str(link.dst.dpid)] = link.dst.port_no;
                net.add_edge(link.src.dpid, link.dst.dpid,info=ports)
                #print("Test: sorce: " + str(link.src.dpid) + ", " + str(link.src.port_no) + "----destination: " + str(link.dst.dpid) + ", " + str(link.dst.port_no) )
        T = nx.minimum_spanning_tree(net)
        return T
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):

        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        dst = eth.dst

        # se ARP esegui proxy arp
        if eth.ethertype == ether_types.ETH_TYPE_ARP:
            #TODO remove comment
            self.proxy_arp(msg)
            return

        # ignora pacchetti non IPv4 (es. ARP, LLDP)
        if eth.ethertype != ether_types.ETH_TYPE_IP:
            return

        '''destination_mac = eth.dst

        # trova switch destinazione
        (dst_dpid, dst_port) = self.find_destination_switch(destination_mac)

        # host non trovato
        if dst_dpid is None:
            # print "DP: ", datapath.id, "Host not found: ", pkt_ip.dst
            return

        if dst_dpid == datapath.id:
            # da usare se l'host e' direttamente collegato
            output_port = dst_port
        else:
            # host non direttamente collegato
            output_port = self.find_next_hop_to_destination(datapath.id,dst_dpid)

        # print "DP: ", datapath.id, "Host: ", pkt_ip.dst, "Port: ", output_port

        # inoltra il pacchetto corrente
        actions = [ parser.OFPActionOutput(output_port) ]
        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=msg.data
        )
        datapath.send_msg(out)

        # aggiungi la regola
        match = parser.OFPMatch(
            eth_dst=destination_mac
            )
        inst = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                [ parser.OFPActionOutput(output_port) ]
            )
        ]
        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=10,
            match=match,
            instructions=inst,
            buffer_id=msg.buffer_id
        )
        datapath.send_msg(mod)
        '''
        T = self.create_tree()
        #print edges
        #print(T.edges.data())
        nodesAndPort = {}
        for (node,data) in T.nodes(data=True):
            nodesAndPort[str(node)] = []
        #Cycle to add rules
        for (nodeSRC,nodeDST, data) in T.edges(data=True):
           # print("DPPID src: " + str(nodeSRC))
            #print("\n")
            #print("DPPID dst: " + str(nodeDST))
            #print("\n")
            #print("Port src: " + str(data["portSRC"]))
            #print("\n")
            #print("Port dst: " + str(data["portDST"]))
            #print("\n")
            nodesAndPort[str(nodeSRC)].append(str(data["info"][str(nodeSRC)]))
            nodesAndPort[str(nodeDST)].append(str(data["info"][str(nodeDST)]))
        #match = parser.OFPMatch()
        match = parser.OFPMatch(eth_dst=dst,eth_src=eth.src)
        # lista di azioni
        # 1. azione FLOOD
        actions = []
        print("Test")

        #print("SWITCH: "+str(datapath.id))
        #print("Info:   ")
        #print(nodesAndPort)
        try:
            for (port) in nodesAndPort[str(datapath.id)]:

                if (int(port) != in_port):
                    # print("Ports cazzo: " + str(port))
                    actions.append(parser.OFPActionOutput(int(port)))
        except:
            print()

        destination_mac = eth.dst

        # trova switch destinazione
        (dst_dpid, dst_port) = self.find_destination_switch(destination_mac)
        #print(dst_dpid)
        for host in get_all_host(self):
            if host.port.dpid == datapath.id:
                if(host.port.port_no != in_port):
                    actions.append(parser.OFPActionOutput(int(host.port.port_no)))
        if dst_dpid is None:
            # print "DP: ", datapath.id, "Host not found: ", pkt_ip.dst
            return
        '''if dst_dpid == datapath.id :
            # da usare se l'host e' direttamente collegato
            output_port = dst_port
            actions = [parser.OFPActionOutput(output_port)]
        '''
        if(len(actions)!=0):
        # lista di istruzioni
        # 1. esegui la lista di azioni immediatamente
            inst = [
                parser.OFPInstructionActions(
                    ofproto.OFPIT_APPLY_ACTIONS,
                    actions
                )
            ]

            # prepara un messaggio Modify-State
            # priorita' 1
            mod = parser.OFPFlowMod(
                datapath=datapath,
                priority=1,
                match=match,
                instructions=inst
            )

            # invia allo switch
            datapath.send_msg(mod)

            assert msg.buffer_id == ofproto.OFP_NO_BUFFER

            out = parser.OFPPacketOut(
                datapath=datapath,
                buffer_id=msg.buffer_id,
                in_port=in_port,
                actions=actions,
                data=msg.data
            )
            datapath.send_msg(out)

            # Add and send rules

        return

    def proxy_arp(self, msg):
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt_in = packet.Packet(msg.data)
        eth_in = pkt_in.get_protocol(ethernet.ethernet)
        arp_in = pkt_in.get_protocol(arp.arp)

        # gestiamo solo i pacchetti ARP REQUEST
        if arp_in.opcode != arp.ARP_REQUEST:
            return

        destination_host_mac = None

        for host in get_all_host(self):
            if arp_in.dst_ip in host.ipv4:
                destination_host_mac = host.mac
                break

        # host non trovato
        if destination_host_mac is None:
            return

        pkt_out = packet.Packet()
        eth_out = ethernet.ethernet(
            dst = eth_in.src,
            src = destination_host_mac,
            ethertype = ether_types.ETH_TYPE_ARP
        )
        arp_out = arp.arp(
            opcode  = arp.ARP_REPLY,
            src_mac = destination_host_mac,
            src_ip  = arp_in.dst_ip,
            dst_mac = arp_in.src_mac,
            dst_ip  = arp_in.src_ip
        )
        pkt_out.add_protocol(eth_out)
        pkt_out.add_protocol(arp_out)
        pkt_out.serialize()

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=ofproto.OFP_NO_BUFFER,
            in_port=ofproto.OFPP_CONTROLLER,
            actions=[parser.OFPActionOutput(in_port)],
            data=pkt_out.data
        )
        datapath.send_msg(out)
        return