import type { Metadata } from "next";
import { RecoveryForm } from "@/components/recovery-form";

export const metadata: Metadata = { title: "Account recovery" };

export default function RecoverPage() {
  return <RecoveryForm />;
}
