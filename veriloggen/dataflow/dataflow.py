from __future__ import absolute_import
from __future__ import print_function
import os
import sys
import copy

import veriloggen.core.vtypes as vtypes
from veriloggen.core.module import Module
from veriloggen.seq.seq import Seq

from . import visitor
from . import dtypes
from . import scheduler
from . import allocator
from . import graph

class Dataflow(object):
    def __init__(self, *nodes, **opts):
        self.datawidth = opts['datawidth'] if 'datawidth' in opts else 32
        self.nodes = set(nodes)
        self.last_result = None
        
    def add(self, *nodes):
        self.nodes.extend(nodes)
    
    #---------------------------------------------------------------------------
    def to_module(self, name, clock='CLK', reset='RST'):
        """ generate a Module definion """
        
        m = Module(name)
        clk = m.Input(clock)
        rst = m.Input(reset)

        m = self.implement(m, clk, rst)

        return m

    #---------------------------------------------------------------------------
    def implement(self, m, clock, reset, seq_name='seq', aswire=False):
        """ implemente actual registers and operations in Verilog """

        seq = Seq(m, seq_name, clock, reset)

        # for mult and div
        m._clock = clock
        m._reset = reset
        
        dataflow_nodes = copy.deepcopy(self.nodes)
        
        input_visitor = visitor.InputVisitor()
        input_vars = set()
        for node in sorted(dataflow_nodes, key=lambda x:x.object_id):
            input_vars.update( input_visitor.visit(node) )

        output_visitor = visitor.OutputVisitor()
        output_vars = set()
        for node in sorted(dataflow_nodes, key=lambda x:x.object_id):
            output_vars.update( output_visitor.visit(node) )

        # add input ports
        for input_var in sorted(input_vars, key=lambda x:x.object_id):
            input_var._implement_input(m, seq)

        # schedule
        sched = scheduler.ASAPScheduler()
        sched.schedule(output_vars)
        
        # balance output stage depth
        max_stage = None
        for output_var in sorted(output_vars, key=lambda x:x.object_id):
            max_stage = dtypes.max(max_stage, output_var.end_stage)

        output_vars = sched.balance_output(output_vars, max_stage)

        # get all vars
        all_visitor = visitor.AllVisitor()
        all_vars = set()
        for output_var in sorted(output_vars, key=lambda x:x.object_id):
            all_vars.update( all_visitor.visit(output_var) )

        # allocate (implement signals)
        alloc = allocator.Allocator()
        alloc.allocate(m, seq, all_vars)

        # add output ports
        for output_var in sorted(output_vars, key=lambda x:x.object_id):
            output_var._implement_output(m, seq)

        # add always statement
        seq.make_always()

        # save schedule result
        self.last_result = output_vars

        return m
            
    #---------------------------------------------------------------------------
    def draw_graph(self, filename='out.png', prog='dot', skip_gap=False):
        if self.last_result is None:
            self.to_module()
            
        graph.draw_graph(self.last_result, filename, prog, skip_gap)
    
    #---------------------------------------------------------------------------
    # Add a new variable
    #---------------------------------------------------------------------------
    def Constant(self, value):
        v = dtypes.Constant(value)
        self.add(v)
        return v
    
    def Variable(self, name=None, valid=None, ready=None, width=32):
        v = dtypes.Variable(name, valid, ready, width)
        self.add(v)
        return v
    
    def Iadd(self, data, initval=None, reset=None, width=32):
        v = dtypes.Iadd(data, initval, reset, width)
        self.add(v)
        return v
    
    def Isub(self, data, initval=None, reset=None, width=32):
        v = dtypes.Isub(data, initval, reset, width)
        self.add(v)
        return v
    
    def Imul(self, data, initval=None, reset=None, width=32):
        v = dtypes.Imul(data, initval, reset, width)
        self.add(v)
        return v
    
    def Idiv(self, data, initval=None, reset=None, width=32):
        v = dtypes.Idiv(data, initval, reset, width)
        self.add(v)
        return v
    
    def Icustom(self, ops, data, initval=None, reset=None, width=32):
        v = dtypes.Icustom(ops, data, initval, reset, width)
        self.add(v)
        return v
