import type {Metadata} from 'next';
import './globals.css';
const origin='https://payobook-people-journeys.groovy-pixie-4012.chatgpt.site';
export const metadata:Metadata={metadataBase:new URL(origin),title:'Payobook | People journeys',description:'Interactive design preview for hiring, probation and holiday planning.',openGraph:{title:'Payobook | People journeys',description:'Hiring, probation and holiday planning in one connected experience.',images:[origin+'/og.png']},twitter:{card:'summary_large_image',title:'Payobook | People journeys',description:'Hiring, probation and holiday planning in one connected experience.',images:[origin+'/og.png']}};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}
