/**
 * extract_schema.ts
 * -------------------
 * Robust Drizzle schema extractor for PostgreSQL + pg-vector.
 *
 * Extracts:
 *  - pgEnum() declarations
 *  - pgTable() declarations
 *  - Base constructor types: text, jsonb, timestamp, boolean, halfvec, bit, ...
 *  - Chained modifiers: notNull, primaryKey, unique, default, defaultNow, references
 *  - Vector dimensions from vector/halfvec/bit
 *  - Enum values from inline arrays and `as const` arrays
 *
 * Outputs: drizzle-schema.json at repo root (or adjust OUT_FILE below).
 */

import {
  ArrayLiteralExpression,
  AsExpression,
  CallExpression,
  Identifier,
  Node,
  ObjectLiteralExpression,
  Project,
  PropertyAssignment,
  SyntaxKind,
  VariableDeclaration,
} from "ts-morph";
import path from "path";
import fs from "fs";

//
// CONFIG
//

const SCHEMA_DIR = path.resolve(__dirname, "../src/lib/db/schemas/");
const OUT_FILE = path.resolve(__dirname, "../../../drizzle-schema.json");

//
// Small helpers
//

function extractLiteral(node: Node | undefined): any {
  if (!node) return undefined;

  switch (node.getKind()) {
    case SyntaxKind.StringLiteral:
      return (node as any).getLiteralValue();
    case SyntaxKind.NumericLiteral:
      return Number((node as any).getLiteralValue());
    case SyntaxKind.TrueKeyword:
      return true;
    case SyntaxKind.FalseKeyword:
      return false;
    default:
      return undefined;
  }
}

/**
 * Resolve value of an identifier, following:
 *   const foo = ["a", "b"] as const;
 *   const foo = ["a", "b"];
 *   const foo = "name";
 */
function resolveIdentifierValue(id: Identifier): any {
  const sym = id.getSymbol();
  if (!sym) return undefined;

  for (const decl of sym.getDeclarations()) {
    if (!Node.isVariableDeclaration(decl)) continue;

    const init = decl.getInitializer();
    if (!init) continue;

    // Handle `[...] as const`
    if (Node.isAsExpression(init)) {
      const asExpr = init as AsExpression;
      const inner = asExpr.getExpression();

      if (Node.isArrayLiteralExpression(inner)) {
        const arr = inner as ArrayLiteralExpression;
        return arr
          .getElements()
          .map((el) => extractLiteral(el))
          .filter((v) => v !== undefined);
      }

      const lit = extractLiteral(inner);
      if (lit !== undefined) return lit;
    }

    // Handle plain array literal
    if (Node.isArrayLiteralExpression(init)) {
      const arr = init as ArrayLiteralExpression;
      return arr
        .getElements()
        .map((el) => extractLiteral(el))
        .filter((v) => v !== undefined);
    }

    // Handle direct literal
    const lit = extractLiteral(init);
    if (lit !== undefined) return lit;
  }

  return undefined;
}

/**
 * Extract string literal or identifier-resolved string.
 */
function extractStringOrIdentifierLiteral(
  node: Node | undefined,
): string | undefined {
  if (!node) return undefined;

  const direct = extractLiteral(node);
  if (typeof direct === "string") return direct;

  if (Node.isIdentifier(node)) {
    const resolved = resolveIdentifierValue(node);
    if (typeof resolved === "string") return resolved;
  }

  return undefined;
}

//
// ENUM extraction
//

type EnumSchema = {
  varName: string; // jobStatusEnum
  name: string; // "job_status"
  values: string[]; // ["pending", "running", ...]
};

function extractEnumFromDeclaration(
  decl: VariableDeclaration,
  call: CallExpression,
): EnumSchema | null {
  const args = call.getArguments();
  if (args.length < 2) return null;

  const enumName = extractStringOrIdentifierLiteral(args[0]);
  if (!enumName) return null;

  const valuesNode = args[1];
  let values: string[] = [];

  if (Node.isArrayLiteralExpression(valuesNode)) {
    const arr = valuesNode as ArrayLiteralExpression;
    values = arr
      .getElements()
      .map((el) => extractLiteral(el))
      .filter((v) => v !== undefined);
  } else if (Node.isIdentifier(valuesNode)) {
    const resolved = resolveIdentifierValue(valuesNode);
    if (Array.isArray(resolved)) {
      values = resolved as string[];
    } else {
      console.warn("⚠ Could not resolve enum values for", enumName);
    }
  } else {
    console.warn(
      "⚠ Unexpected enum values node for",
      enumName,
      "kind:",
      valuesNode.getKindName(),
    );
  }

  return {
    varName: decl.getName(),
    name: enumName,
    values,
  };
}

//
// Call chain utilities
//

/**
 * For a call like: text("id").notNull().defaultNow()
 * returns array [outermostCall (defaultNow), middleCall (notNull), rootCall (text)].
 */
function getCallChain(call: CallExpression): CallExpression[] {
  const chain: CallExpression[] = [];
  let current: CallExpression | undefined = call;

  while (current) {
    chain.push(current);
    const expr = current.getExpression();

    if (Node.isPropertyAccessExpression(expr)) {
      const inner = expr.getExpression();
      if (Node.isCallExpression(inner)) {
        current = inner;
        continue;
      }
    }

    break;
  }

  return chain;
}

/**
 * Get the name of the base constructor from the *root* call in the chain:
 *   text("id").notNull().defaultNow()  → "text"
 *   jobStatusEnum("status").notNull()  → "jobStatusEnum"
 */
function getConstructorNameFromRoot(rootCall: CallExpression): string {
  const expr = rootCall.getExpression();

  if (Node.isIdentifier(expr)) return expr.getText();
  if (Node.isPropertyAccessExpression(expr)) return expr.getName();

  return expr.getText();
}

//
// TABLE extraction
//

type ForeignKeyInfo = {
  tableVar: string;
  column: string;
  onDelete?: string;
};

type ColumnSchema = {
  name: string;
  dbName: string;
  drizzleType: string;
  nullable: boolean;
  primaryKey: boolean;
  defaultRandom: boolean;
  array: boolean;
  unique: boolean;
  hasDefault: boolean;
  vectorDims?: number;
  enumVar?: string;
  fk?: ForeignKeyInfo;
};

type TableSchema = {
  tableName: string;
  columns: ColumnSchema[];
};

function extractColumn(
  prop: PropertyAssignment,
  enumVarsByName: Map<string, EnumSchema>,
): ColumnSchema | null {
  const name = prop.getName();
  const init = prop.getInitializer();
  if (!init || !Node.isCallExpression(init)) return null;

  const chain = getCallChain(init);
  const rootCall = chain[chain.length - 1]; // the innermost call
  const rootCtorName = getConstructorNameFromRoot(rootCall);

  // init column name: first arg of root constructor, or fallback to prop name
  const rootArgs = rootCall.getArguments();
  let dbName: string = name;
  if (rootArgs.length > 0) {
    dbName = extractStringOrIdentifierLiteral(rootArgs[0]) || name;
  }

  let nullable = true;
  let primaryKey = false;
  let unique = false;
  let hasDefault = false;
  let array = false;
  let vectorDims: number | undefined;
  let enumVar: string | undefined;
  let fk: ForeignKeyInfo | undefined;
  let defaultRandom = false;

  // detect enum var: if ctor is a varName of a pgEnum
  if (enumVarsByName.has(rootCtorName)) {
    enumVar = rootCtorName;
  }

  // vector dims for vector/halfvec/bit
  if (["vector", "halfvec", "bit"].includes(rootCtorName)) {
    const cfgArg = rootArgs[1];
    if (cfgArg && Node.isObjectLiteralExpression(cfgArg)) {
      const obj = cfgArg as ObjectLiteralExpression;
      const dimProp = obj.getProperty("dimensions");
      if (dimProp && Node.isPropertyAssignment(dimProp)) {
        const dimVal = extractLiteral(dimProp.getInitializer());
        if (typeof dimVal === "number") {
          vectorDims = dimVal;
        }
      }
    }
  }

  // traverse chain modifiers (outermost to root)
  for (const call of chain.slice(0, -1)) {
    const expr = call.getExpression();
    if (!Node.isPropertyAccessExpression(expr)) continue;

    const nameText = expr.getName();

    if (nameText === "defaultRandom") {
      defaultRandom = true;
    } else if (nameText === "array") {
      array = true;
    } else if (nameText === "notNull") {
      nullable = false;
    } else if (nameText === "primaryKey") {
      primaryKey = true;
      nullable = false;
    } else if (nameText === "unique") {
      unique = true;
    } else if (nameText === "default" || nameText === "defaultNow") {
      hasDefault = true;
    } else if (nameText === "references") {
      // references(() => Table.id, { onDelete })
      const args = call.getArguments();
      const fnArg = args[0];
      if (fnArg && Node.isArrowFunction(fnArg)) {
        const body = fnArg.getBody();
        const txt = body.getText(); // "SomeTable.id"
        const [tbl, col] = txt.split(".");
        fk = { tableVar: tbl, column: col };
      }
      const optArg = args[1];
      if (optArg && Node.isObjectLiteralExpression(optArg)) {
        const obj = optArg as ObjectLiteralExpression;
        const onDelProp = obj.getProperty("onDelete");
        if (onDelProp && Node.isPropertyAssignment(onDelProp)) {
          const val = extractStringOrIdentifierLiteral(
            onDelProp.getInitializer(),
          );
          if (val) {
            if (!fk) fk = { tableVar: "", column: "" };
            fk.onDelete = val;
          }
        }
      }
    }
    // We intentionally ignore $type, $onUpdate, etc. here
  }

  const drizzleType = rootCtorName;

  return {
    name,
    dbName,
    drizzleType,
    defaultRandom,
    array,
    nullable,
    primaryKey,
    unique,
    hasDefault,
    vectorDims,
    enumVar,
    fk,
  };
}

function extractTableFromDeclaration(
  call: CallExpression,
  enumVarsByName: Map<string, EnumSchema>,
): TableSchema | null {
  const args = call.getArguments();
  if (args.length < 2) return null;

  const tableNameNode = args[0];
  const tableName = extractStringOrIdentifierLiteral(tableNameNode);
  if (!tableName) return null;

  const colsObj = args[1];
  if (!Node.isObjectLiteralExpression(colsObj)) return null;

  const props = colsObj.getProperties();
  const columns: ColumnSchema[] = [];

  for (const p of props) {
    if (!Node.isPropertyAssignment(p)) continue;
    const col = extractColumn(p, enumVarsByName);
    if (col) columns.push(col);
  }

  return { tableName, columns };
}

//
// MAIN
//

function main() {
  const project = new Project({
    // tsConfigFilePath: path.resolve(__dirname, "../tsconfig.json"),
  });

  project.addSourceFilesAtPaths(`${SCHEMA_DIR}/**/*.ts`);

  const enums: EnumSchema[] = [];
  const enumVarsByName = new Map<string, EnumSchema>();
  const tables: TableSchema[] = [];

  // Pass 1: collect enums
  for (const file of project.getSourceFiles()) {
    for (const decl of file.getVariableDeclarations()) {
      const init = decl.getInitializer();
      if (!init || !Node.isCallExpression(init)) continue;

      const exprText = init.getExpression().getText();
      if (exprText !== "pgEnum") continue;

      const info = extractEnumFromDeclaration(decl, init);
      if (info) {
        enums.push(info);
        enumVarsByName.set(info.varName, info);
      }
    }
  }

  // Pass 2: collect tables
  for (const file of project.getSourceFiles()) {
    for (const decl of file.getVariableDeclarations()) {
      const init = decl.getInitializer();
      if (!init || !Node.isCallExpression(init)) continue;

      const exprText = init.getExpression().getText();
      // if (exprText !== "pgTable") continue;
      if (!["pgTable", "pgMaterializedView", "pgView"].includes(exprText))
        continue;

      const table = extractTableFromDeclaration(init, enumVarsByName);
      if (table) {
        tables.push(table);
      }
    }
  }

  const schema = {
    enums,
    tables,
  };

  fs.writeFileSync(OUT_FILE, JSON.stringify(schema, null, 2));
  console.log("✔ Extracted schema →", OUT_FILE);
}

main();
