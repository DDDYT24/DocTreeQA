"""Optional ANTLR syntax check; this cannot compile Excel objects or execute macros."""

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
GRAMMAR_BLOBS = {
    "vbaLexer.g4": "1bc3e0a76567d9046df8693aa4ed2ddde0271130",
    "vbaParser.g4": "cf6e17f25a4212745a10af612d9c52db0ddab1e3",
}
ANTLR_SHA256 = "eae2dfa119a64327444672aff63e9ec35a20180dc5b8090b7a6ab85125df4d76"
RUNNER = """
import org.antlr.v4.runtime.*;
import java.nio.file.Path;
public class CheckVba {
    static class Errors extends BaseErrorListener {
        int count = 0;
        @Override public void syntaxError(Recognizer<?, ?> recognizer, Object offendingSymbol,
                int line, int position, String msg, RecognitionException e) {
            count++;
            System.err.println(line + ":" + position + " " + msg);
        }
    }
    public static void main(String[] args) throws Exception {
        Errors errors = new Errors();
        vbaLexer lexer = new vbaLexer(CharStreams.fromPath(Path.of(args[0])));
        lexer.removeErrorListeners();
        lexer.addErrorListener(errors);
        vbaParser parser = new vbaParser(new CommonTokenStream(lexer));
        parser.removeErrorListeners();
        parser.addErrorListener(errors);
        parser.startRule();
        System.out.println("{\\"syntax_errors\\":" + errors.count + "}");
        if (errors.count != 0) System.exit(1);
    }
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grammar-dir", type=Path, required=True)
    parser.add_argument("--antlr-jar", type=Path, required=True)
    args = parser.parse_args()
    jar = args.antlr_jar.resolve()
    if hashlib.sha256(jar.read_bytes()).hexdigest() != ANTLR_SHA256:
        raise ValueError("Expected the pinned ANTLR complete JAR")
    with TemporaryDirectory(prefix="doctree-vba-syntax-") as folder:
        work = Path(folder)
        for name, expected in GRAMMAR_BLOBS.items():
            data = (args.grammar_dir / name).read_bytes()
            digest = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            if digest != expected:
                raise ValueError(f"Unexpected grammar blob: {name}")
            (work / name).write_bytes(data)
        (work / "CheckVba.java").write_text(RUNNER)

        def run(arguments, *, check=True):
            return subprocess.run(arguments, cwd=work, check=check, capture_output=True, text=True)

        run(["java", "-jar", str(jar), *GRAMMAR_BLOBS])
        run(
            [
                "java",
                "com.sun.tools.javac.Main",
                "-cp",
                str(jar),
                *[str(p) for p in work.glob("*.java")],
            ]
        )
        command = ["java", "-cp", str(work) + os.pathsep + str(jar), "CheckVba"]
        source = ROOT / "vba/DocTreeQA.bas"
        result = json.loads(run([*command, str(source)]).stdout)
        invalid = work / "invalid.bas"
        invalid.write_text("Public Sub Broken(\nEnd Sub\n")
        rejected = run([*command, str(invalid)], check=False)
        if rejected.returncode == 0 or json.loads(rejected.stdout)["syntax_errors"] == 0:
            raise ValueError("Parser failed to reject an intentionally invalid module")
        result.update(
            status="passed",
            module_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            parser="ANTLR 4.13.2; grammars-v4 VBA 7.1 startRule",
            grammar_repository="https://github.com/antlr/grammars-v4/tree/master/vba/vba7_1",
            grammar_blobs=GRAMMAR_BLOBS,
            antlr_jar_sha256=ANTLR_SHA256,
            invalid_syntax_control_rejected=True,
            scope=(
                "Grammar syntax only. Excel object binding, compilation and execution not tested."
            ),
            windows_excel_compile="Not run",
            windows_excel_execution="Not run",
        )
        (ROOT / "reports/vba_syntax_check.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
