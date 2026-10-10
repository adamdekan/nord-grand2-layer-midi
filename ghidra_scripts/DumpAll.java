// Dump decompiled C for every function plus string->referrer map.
// Args: <outdir>
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.app.decompiler.parallel.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.address.*;
import ghidra.program.model.data.*;
import ghidra.util.task.TaskMonitor;
import java.io.*;
import java.util.*;

public class DumpAll extends GhidraScript {
    @Override
    public void run() throws Exception {
        String outdir = getScriptArgs()[0];
        new File(outdir).mkdirs();
        Listing listing = currentProgram.getListing();
        ReferenceManager rm = currentProgram.getReferenceManager();
        FunctionManager fm = currentProgram.getFunctionManager();

        try (PrintWriter sw = new PrintWriter(new FileWriter(outdir + "/strings_xrefs.txt"))) {
            DataIterator it = listing.getDefinedData(true);
            while (it.hasNext()) {
                Data d = it.next();
                if (!(d.getDataType() instanceof StringDataType || d.getDataType() instanceof TerminatedStringDataType
                      || d.getDataType().getName().toLowerCase().contains("string"))) continue;
                Object v = d.getValue();
                StringBuilder sb = new StringBuilder();
                sb.append(d.getAddress()).append(" \"").append(String.valueOf(v).replace("\n","\\n")).append("\"");
                for (Reference r : rm.getReferencesTo(d.getAddress())) {
                    Function f = fm.getFunctionContaining(r.getFromAddress());
                    sb.append(" | ").append(r.getFromAddress()).append(f != null ? "(" + f.getName() + ")" : "");
                }
                sw.println(sb);
            }
        }

        List<Function> funcs = new ArrayList<>();
        for (Function f : fm.getFunctions(true)) funcs.add(f);
        println("functions: " + funcs.size());

        DecompileConfigurer cfg = d -> {
            DecompileOptions o = new DecompileOptions();
            d.setOptions(o);
            d.toggleCCode(true);
            d.toggleSyntaxTree(false);
            d.setSimplificationStyle("decompile");
        };
        DecompilerCallback<String> cb = new DecompilerCallback<String>(currentProgram, cfg) {
            @Override
            public String process(DecompileResults r, TaskMonitor m) {
                Function f = r.getFunction();
                String c = r.getDecompiledFunction() != null ? r.getDecompiledFunction().getC() : "/* decompile failed: " + r.getErrorMessage() + " */";
                return "//==== " + f.getName() + " @ " + f.getEntryPoint() + "\n" + c + "\n";
            }
        };
        cb.setTimeout(60);
        List<String> res = ParallelDecompiler.decompileFunctions(cb, funcs, monitor);
        cb.dispose();
        res.sort(Comparator.comparing(s -> s.substring(s.indexOf(" @ ") + 3, s.indexOf("\n"))));
        try (PrintWriter w = new PrintWriter(new FileWriter(outdir + "/decomp.c"))) {
            for (String s : res) w.println(s);
        }
        println("done");
    }
}
