import { useState, type FormEvent } from 'react'
import { Send } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { EmptyLine, ErrorLine, MockPage, SkeletonRows, shortDate } from '@/components/mock/MockPrimitives'
import { useSellerMessages, useSellerReply } from '@/hooks/useMock'
import { cn } from '@/utils/cn'

export default function SellerMessagesPage() {
  const threads = useSellerMessages()
  const reply = useSellerReply()
  const [selected, setSelected] = useState<string | null>(null)
  const [text, setText] = useState('')
  const active = threads.data?.find((thread) => thread.id === (selected ?? threads.data?.[0]?.id))

  const send = async (event: FormEvent) => {
    event.preventDefault()
    if (!active || !text.trim()) return
    await reply.mutateAsync({ id: active.id, text })
    setText('')
  }

  return (
    <MockPage title="Tin nhắn" description="Trả lời câu hỏi của người mua. Người mua giả lập sẽ phản hồi sau vài giây.">
      {threads.isLoading ? <SkeletonRows /> : threads.isError ? <ErrorLine error={threads.error} /> : !active ? <EmptyLine>Chưa có cuộc trò chuyện nào.</EmptyLine> : (
        <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
          <ul className="surface-card divide-y divide-line overflow-hidden" aria-label="Cuộc trò chuyện">
            {threads.data?.map((thread) => (
              <li key={thread.id}>
                <button type="button" onClick={() => setSelected(thread.id)} aria-current={thread.id === active.id} className={cn('focus-ring block w-full px-4 py-3 text-left hover:bg-ground', thread.id === active.id && 'bg-primary-50')}>
                  <span className="flex items-center justify-between text-sm font-semibold">{thread.buyer}{thread.unread && <span className="h-2 w-2 rounded-full bg-price" aria-label="Chưa đọc" />}</span>
                  <span className="mt-0.5 block truncate text-xs text-muted">{thread.product}</span>
                </button>
              </li>
            ))}
          </ul>
          <section className="surface-card flex min-h-[420px] flex-col" aria-label={`Trò chuyện với ${active.buyer}`}>
            <header className="border-b border-line px-4 py-3"><p className="font-semibold">{active.buyer}</p><p className="text-xs text-muted">Về: {active.product}</p></header>
            <ol className="flex-1 space-y-3 overflow-y-auto p-4" aria-live="polite">
              {active.messages.map((message, index) => (
                <li key={index} className={cn('flex', message.from === 'seller' ? 'justify-end' : 'justify-start')}>
                  <div className={cn('max-w-[80%] rounded-card px-3 py-2 text-sm', message.from === 'seller' ? 'bg-primary-600 text-white' : 'bg-slate-100')}>
                    <p>{message.text}</p>
                    <time dateTime={message.at} className={cn('mt-1 block text-[11px]', message.from === 'seller' ? 'text-primary-100' : 'text-muted')}>{shortDate(message.at)}</time>
                  </div>
                </li>
              ))}
            </ol>
            <form onSubmit={send} className="flex gap-2 border-t border-line p-3">
              <label htmlFor="reply" className="sr-only">Nội dung trả lời</label>
              <input id="reply" value={text} onChange={(e) => setText(e.target.value)} maxLength={500} placeholder="Nhập tin nhắn…" className="focus-ring h-11 min-w-0 flex-1 rounded-md border border-slate-300 px-3 text-sm" />
              <Button type="submit" loading={reply.isPending} disabled={!text.trim()} aria-label="Gửi tin nhắn"><Send className="h-4 w-4" /></Button>
            </form>
            {reply.error && <div className="px-3 pb-3"><ErrorLine error={reply.error} /></div>}
          </section>
        </div>
      )}
    </MockPage>
  )
}
