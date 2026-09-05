import { loader } from "fumadocs-core/source";
import { pageSchema } from "fumadocs-core/source/schema";
import { defineDocs } from "fumadocs-mdx/macro";
import { z } from "zod";

export const learnSections = [
  "start-here",
  "concepts",
  "guides",
  "reference",
  "troubleshooting",
] as const;

export type LearnSection = (typeof learnSections)[number];

const articleSchema = pageSchema.extend({
  content_id: z.string().min(1),
  section: z.enum(learnSections),
  order: z.number().int().nonnegative(),
  audiences: z.array(z.string()).min(1),
  permissions: z.array(z.string()),
  owner: z.string().min(1),
  status: z.enum([
    "outline",
    "draft",
    "technical-review",
    "product-review",
    "approved",
    "retired",
  ]),
  last_verified: z.string().date(),
  review_by: z.string().date(),
  verified_by: z.array(z.string()).min(1),
  reading_time: z.number().int().positive(),
  prerequisites: z.array(z.string()).default([]),
});

const docs = defineDocs({
  dir: "content/learn",
  docs: {
    schema: articleSchema,
  },
});

export const learnSource = loader({
  baseUrl: "/learn",
  source: docs.toFumadocsSource(),
});

export type LearnPage = (typeof learnSource)["$inferPage"];

const sectionLabels: Record<LearnSection, string> = {
  "start-here": "Start here",
  concepts: "Core concepts",
  guides: "How-to guides",
  reference: "Feature reference",
  troubleshooting: "Troubleshooting",
};

export function labelForLearnSection(section: LearnSection) {
  return sectionLabels[section];
}

export function getOrderedLearnPages() {
  return learnSource.getPages()
    .filter((page) => page.slugs.length > 0 && page.data.status !== "retired")
    .sort((left, right) => {
      const sectionDelta = learnSections.indexOf(left.data.section) - learnSections.indexOf(right.data.section);
      return sectionDelta || left.data.order - right.data.order || left.data.title.localeCompare(right.data.title);
    });
}

export function getLearnNavigation() {
  const pages = getOrderedLearnPages();
  return learnSections.map((section) => ({
    section,
    label: sectionLabels[section],
    pages: pages.filter((page) => page.data.section === section),
  }));
}
