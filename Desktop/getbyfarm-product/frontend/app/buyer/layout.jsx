import { RoleLayout } from "@/components/Session";

export default function Layout({ children }) {
  return <RoleLayout role="buyer">{children}</RoleLayout>;
}
