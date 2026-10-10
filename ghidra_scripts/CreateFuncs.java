// Create functions at every code pointer found in data (vtables, callback tables,
// literal pools), then re-run auto-analysis.  Args: <codeStart> <codeEnd> <dataEnd> (hex)
import ghidra.app.script.GhidraScript;
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import java.util.*;

public class CreateFuncs extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs();
        long cs = Long.parseLong(a[0], 16), ce = Long.parseLong(a[1], 16), de = Long.parseLong(a[2], 16);
        Memory mem = currentProgram.getMemory();
        Listing listing = currentProgram.getListing();
        AddressSpace sp = currentProgram.getAddressFactory().getDefaultAddressSpace();
        TreeSet<Long> targets = new TreeSet<>();
        for (long p = cs; p + 4 <= de; p += 4) {
            Address pa = sp.getAddress(p);
            if (p < ce && listing.getInstructionContaining(pa) != null) continue;
            int v;
            try { v = mem.getInt(pa); } catch (Exception e) { continue; }
            long u = v & 0xffffffffL;
            if (u >= cs && u < ce && (u & 3) == 0) targets.add(u);
        }
        println("candidate targets: " + targets.size());
        int made = 0;
        for (long t : targets) {
            Address ta = sp.getAddress(t);
            if (currentProgram.getFunctionManager().getFunctionAt(ta) != null) continue;
            if (listing.getInstructionAt(ta) == null) {
                if (listing.getDefinedDataContaining(ta) != null) continue;
                DisassembleCommand dc = new DisassembleCommand(ta, null, true);
                dc.applyTo(currentProgram, monitor);
                if (listing.getInstructionAt(ta) == null) continue;
            }
            if (currentProgram.getFunctionManager().getFunctionContaining(ta) != null
                && currentProgram.getFunctionManager().getFunctionContaining(ta).getEntryPoint().getOffset() != t) {
                // pointer into the middle of an existing function: likely a label, skip
                continue;
            }
            if (new CreateFunctionCmd(ta).applyTo(currentProgram, monitor)) made++;
        }
        println("functions created: " + made);
        analyzeChanges(currentProgram);
        println("total functions: " + currentProgram.getFunctionManager().getFunctionCount());
    }
}
