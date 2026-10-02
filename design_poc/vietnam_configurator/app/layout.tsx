import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { metadataBase: new URL('https://payobook-vietnam-configuration-lab.groovy-pixie-4012.chatgpt.site'), title: 'Payobook · Vietnam configuration lab', description: 'Design prototype: turn Vietnam earnings, deductions and benefits into a payroll schema.', openGraph: {title:'Vietnam configuration lab', description:'Earnings · Deductions · Benefits', images:['/og.png']}, twitter: {card:'summary_large_image', title:'Vietnam configuration lab', description:'Earnings · Deductions · Benefits', images:['/og.png']} };
export default function RootLayout({children}: Readonly<{children: React.ReactNode}>) { return <html lang="en"><body>{children}</body></html>; }
