import Link from "next/link";
import { BrandMark, ArrowRightIcon, FileIcon } from "@/components/ui/icons";
import "./styles.css";

export default function LoginPage() {
  return <main className="access-page"><div className="access-card">
    <Link href="/home" className="access-brand"><BrandMark />Prose</Link>
    <div className="access-mark"><FileIcon width={32} height={32} /></div>
    <h1>从理解要求，到写好应答。</h1>
    <p>让招标文件成为清楚、可核验的工作清单。</p>
    <Link href="/home" className="access-enter">进入工作区<ArrowRightIcon width={18} height={18} /></Link>
    <div className="access-note">当前环境采用工作区访问，暂不提供账号登录。</div>
  </div></main>;
}
