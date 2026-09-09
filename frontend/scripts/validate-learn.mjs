import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = path.resolve(frontendRoot, "..");
const contentRoot = path.join(frontendRoot, "content", "learn");
const sections = ["concepts", "policyos", "practice"];
const conceptSubsections = new Set([
  "From decisions to assignments",
  "How policies combine",
  "Groups and exceptions",
  "Change, time, and evidence",
  "People, accounts, and access",
  "Controlled access",
]);
const statuses = ["outline", "draft", "technical-review", "product-review", "approved", "retired"];
const required = [
  "title",
  "description",
  "content_id",
  "section",
  "order",
  "audiences",
  "permissions",
  "owner",
  "status",
  "last_verified",
  "review_by",
  "verified_by",
  "reading_time",
  "prerequisites",
];
const failures = [];
const warnings = [];

function walk(directory, extension) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const item = path.join(directory, entry.name);
    if (entry.isDirectory()) return walk(item, extension);
    return entry.name.endsWith(extension) ? [item] : [];
  });
}

function relative(file) {
  return path.relative(repoRoot, file);
}

function fail(file, message) {
  failures.push(`${relative(file)}: ${message}`);
}

function readFrontmatter(file) {
  const source = fs.readFileSync(file, "utf8");
  const match = source.match(/^---\n([\s\S]*?)\n---\n/);
  if (!match) {
    fail(file, "missing YAML frontmatter");
    return { data: {}, body: source };
  }
  try {
    return { data: parse(match[1]), body: source.slice(match[0].length) };
  } catch (error) {
    fail(file, `invalid YAML: ${error.message}`);
    return { data: {}, body: source };
  }
}

const ownerRegistryFile = path.join(repoRoot, "docs", "learn", "content-owners.yml");
const ownerRegistry = parse(fs.readFileSync(ownerRegistryFile, "utf8"));
if (!Array.isArray(ownerRegistry.owners))
  throw new Error("content-owners.yml must define an owners list");
for (const owner of ownerRegistry.owners) {
  if (
    typeof owner.name !== "string" ||
    typeof owner.area !== "string" ||
    !["quarterly", "semiannual"].includes(owner.cadence)
  ) {
    failures.push(
      `${relative(ownerRegistryFile)}: every owner needs a name, area, and valid cadence`,
    );
  }
}
const owners = new Set(ownerRegistry.owners.map((owner) => owner.name));
if (owners.size !== ownerRegistry.owners.length)
  failures.push(`${relative(ownerRegistryFile)}: owner names must be unique`);
const files = walk(contentRoot, ".mdx");
const articles = files.map((file) => ({ file, ...readFrontmatter(file) }));
const ids = new Map();
const titles = new Set(articles.map(({ data }) => data.title).filter(Boolean));
const routes = new Set(["/learn"]);

for (const article of articles) {
  const { file, data, body } = article;
  for (const field of required)
    if (data[field] === undefined || data[field] === null)
      fail(file, `missing required field ${field}`);
  if (!sections.includes(data.section)) fail(file, `unknown section ${data.section}`);
  if (data.section === "concepts" && path.basename(file) !== "index.mdx") {
    if (!conceptSubsections.has(data.subsection))
      fail(file, `unknown or missing Concepts subsection ${JSON.stringify(data.subsection)}`);
  } else if (data.subsection !== undefined) {
    fail(file, "subsection is currently supported only for Concepts lessons");
  }
  if (!statuses.includes(data.status)) fail(file, `unknown status ${data.status}`);
  if (!owners.has(data.owner)) fail(file, `owner ${JSON.stringify(data.owner)} is not registered`);
  if (!Array.isArray(data.audiences) || data.audiences.length === 0)
    fail(file, "audiences must not be empty");
  if (!Array.isArray(data.permissions)) fail(file, "permissions must be a list");
  if (!Array.isArray(data.verified_by) || data.verified_by.length === 0)
    fail(file, "verified_by must not be empty");
  if (!Array.isArray(data.prerequisites)) fail(file, "prerequisites must be a list");
  if (
    !Number.isInteger(data.reading_time) ||
    data.reading_time < 0 ||
    (data.status !== "outline" && data.reading_time === 0)
  )
    fail(file, "reading_time must be positive for authored articles or zero for outlines");
  for (const prerequisite of data.prerequisites ?? [])
    if (!titles.has(prerequisite))
      fail(file, `unknown prerequisite title ${JSON.stringify(prerequisite)}`);
  for (const evidence of data.verified_by ?? []) {
    if (path.isAbsolute(evidence) || evidence.includes(".."))
      fail(file, `unsafe verified_by path ${evidence}`);
    else if (!fs.existsSync(path.join(repoRoot, evidence)))
      fail(file, `verified_by target does not exist: ${evidence}`);
  }
  if (ids.has(data.content_id))
    fail(
      file,
      `duplicate content_id ${data.content_id} (also ${relative(ids.get(data.content_id))})`,
    );
  else ids.set(data.content_id, file);

  const lastVerified = new Date(`${data.last_verified}T00:00:00Z`);
  const reviewBy = new Date(`${data.review_by}T00:00:00Z`);
  if (Number.isNaN(lastVerified.valueOf()) || Number.isNaN(reviewBy.valueOf()))
    fail(file, "review dates must use YYYY-MM-DD");
  else {
    const days = (reviewBy - lastVerified) / 86_400_000;
    const maximum = ["concepts", "reference"].includes(data.section) ? 185 : 95;
    if (reviewBy < lastVerified) fail(file, "review_by precedes last_verified");
    if (days > maximum) fail(file, `review interval is ${days} days; maximum is ${maximum}`);
    if (data.review_by < new Date().toISOString().slice(0, 10))
      fail(file, `content review is overdue (${data.review_by})`);
  }
  if (!["approved", "retired"].includes(data.status))
    warnings.push(`${data.content_id} remains ${data.status} (${data.owner})`);

  const rel = path
    .relative(contentRoot, file)
    .replace(/\.mdx$/, "")
    .split(path.sep);
  const route = rel.join("/") === "index" ? "/learn" : `/learn/${rel.join("/")}`;
  routes.add(route);
  article.route = route;
  article.links = [
    ...body.matchAll(/(?:\]\(|href=["'])(\/learn(?:\/[a-z0-9-]+){0,2})(?:#[^)'"\s]+)?/g),
  ].map((match) => match[1].replace(/\/$/, ""));
}

for (const { file, links = [] } of articles)
  for (const link of links) if (!routes.has(link)) fail(file, `broken learning link ${link}`);

const redirectsFile = path.join(frontendRoot, "lib", "learn-redirects.json");
const redirects = JSON.parse(fs.readFileSync(redirectsFile, "utf8"));
for (const [source, destination] of Object.entries(redirects)) {
  if (routes.has(source)) fail(redirectsFile, `redirect shadows a current lesson: ${source}`);
  if (!routes.has(destination))
    fail(redirectsFile, `redirect destination does not exist: ${destination}`);
}

for (const section of sections) {
  const metaFile = path.join(contentRoot, section, "meta.json");
  let pages;
  try {
    pages = JSON.parse(fs.readFileSync(metaFile, "utf8")).pages;
  } catch (error) {
    fail(metaFile, `invalid metadata: ${error.message}`);
    continue;
  }
  const expected = articles
    .filter(
      (article) => article.data.section === section && path.basename(article.file) !== "index.mdx",
    )
    .map((article) => path.basename(article.file, ".mdx"));
  for (const slug of expected)
    if (pages.filter((item) => item === slug).length !== 1)
      fail(metaFile, `${slug} must appear exactly once`);
  for (const slug of pages)
    if (!expected.includes(slug)) fail(metaFile, `unknown or misclassified page ${slug}`);
}

const rootMetaFile = path.join(contentRoot, "meta.json");
const rootPages = JSON.parse(fs.readFileSync(rootMetaFile, "utf8")).pages;
for (const requiredPage of ["index", ...sections])
  if (rootPages.filter((item) => item === requiredPage).length !== 1)
    fail(rootMetaFile, `${requiredPage} must appear exactly once`);

const sourceFiles = walk(path.join(frontendRoot, "app"), ".tsx").concat(
  walk(path.join(frontendRoot, "components"), ".tsx"),
);
for (const file of sourceFiles) {
  const source = fs.readFileSync(file, "utf8");
  for (const match of source.matchAll(/(?:href=|href:)\s*["'](\/learn(?:\/[a-z0-9-]+){0,2})/g)) {
    if (!routes.has(match[1])) fail(file, `broken contextual learning link ${match[1]}`);
  }
}

if (failures.length) {
  console.error(
    `Learn quality gate failed with ${failures.length} problem(s):\n- ${failures.join("\n- ")}`,
  );
  process.exit(1);
}

const ownerCounts = new Map();
for (const { data } of articles)
  ownerCounts.set(data.owner, (ownerCounts.get(data.owner) ?? 0) + 1);
console.log(
  `Learn quality gate passed: ${articles.length} articles, ${routes.size} routes, ${owners.size} registered owners.`,
);
console.log(
  `Ownership: ${[...ownerCounts]
    .sort()
    .map(([owner, count]) => `${owner} (${count})`)
    .join(", ")}`,
);
if (warnings.length)
  console.log(`Review queue: ${warnings.length} article(s) await organizational approval.`);
