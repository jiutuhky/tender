import "./globals.css";

export const metadata = {
  title: "Hagent",
  description: "Hagent — Web-based agent harness",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="h-screen bg-gray-50 text-gray-900">
        {children}
      </body>
    </html>
  );
}
