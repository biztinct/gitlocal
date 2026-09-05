import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = {metadataBase:new URL('https://payobook-workforce-futures.groovy-pixie-4012.chatgpt.site'),title:'Workforce Futures | Payobook Design Lab',description:'Three interactive concepts for intuitive workforce planning. Explore staffing, profit, growth and shift coverage.',openGraph:{images:['/og.png'],title:'Workforce Futures',description:'Better people decisions, beautifully simple.'},twitter:{images:['/og.png'],card:'summary_large_image',title:'Workforce Futures',description:'Better people decisions, beautifully simple.'}};
export default function RootLayout({children}:Readonly<{children:React.ReactNode}>) {return <html lang="en"><body>{children}</body></html>}
