import type { Metadata } from "next";
import { RecoveryForm } from "./_components/recovery-form/recovery-form";

export const metadata: Metadata = { title: "Account recovery" };

export default function RecoverPage() {
  return <RecoveryForm />;
}
