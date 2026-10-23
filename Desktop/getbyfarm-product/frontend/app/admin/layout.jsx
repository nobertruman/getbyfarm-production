import { RoleLayout } from "@/components/Session";

export default function Layout({ children }) {
  return <RoleLayout role="admin">{children}</RoleLayout>;
}
