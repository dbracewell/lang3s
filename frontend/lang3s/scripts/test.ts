import * as ts from "typescript";
import * as fs from "fs";

// Read the TypeScript file
const fileName =
  "/Users/ik/prj/Lang3s/frontend/lang3s/src/lib/db/schemas/views.ts";
const sourceCode = fs.readFileSync(fileName, "utf-8");

// Parse the file
const sourceFile = ts.createSourceFile(
  fileName, // file name
  sourceCode, // file content
  ts.ScriptTarget.Latest, // JS version target
  true, // setParentNodes
);

// Walk the AST recursively
function visit(node: ts.Node) {
  const nodeType = ts.SyntaxKind[node.kind];
  const firstToken = node.getFirstToken()?.getText();
  if (nodeType === "CallExpression" && firstToken === "pgMaterializedView") {
    console.log(firstToken);
    ts.forEachChild(node, (n) => {
      console.log(ts.SyntaxKind[n.kind], n.getText());
    });
  } else {
    ts.forEachChild(node, visit);
  }
}

visit(sourceFile);
