import { Inbox } from 'lucide-react'

export default function WorkspacePlaceholderPage() { return <div className="flex min-h-96 flex-col items-center justify-center rounded-card border border-dashed border-slate-300 bg-slate-50 p-8 text-center"><span className="flex h-16 w-16 items-center justify-center rounded-full bg-white text-primary-500 shadow-soft"><Inbox className="h-8 w-8" /></span><h1 className="mt-5 text-xl font-extrabold">Chưa có dữ liệu</h1><p className="mt-2 max-w-md text-sm leading-6 text-slate-500">Các bản ghi mới sẽ xuất hiện tại đây khi phát sinh hoạt động.</p></div> }
