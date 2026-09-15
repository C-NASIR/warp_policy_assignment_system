import type { Metadata } from "next";
import { getOAuthAuthorizationRequest } from "@/lib/backend";
import { OAuthConsent } from "./oauth-consent";

export const metadata: Metadata = { title: "Authorize agent access" };

type SearchParameters = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function OAuthAuthorizePage({
  searchParams,
}: {
  searchParams: Promise<SearchParameters>;
}) {
  const values = await searchParams;
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    for (const item of Array.isArray(value) ? value : value ? [value] : []) query.append(key, item);
  }
  const request = await getOAuthAuthorizationRequest(query.toString());
  const responseType = first(values.response_type);
  const codeChallenge = first(values.code_challenge);
  const challengeMethod = first(values.code_challenge_method);
  if (responseType !== "code" || !codeChallenge || challengeMethod !== "S256") {
    throw new Error("The agent supplied an invalid OAuth authorization request.");
  }
  return (
    <OAuthConsent
      request={{
        ...request,
        response_type: responseType,
        code_challenge: codeChallenge,
        code_challenge_method: challengeMethod,
      }}
    />
  );
}
