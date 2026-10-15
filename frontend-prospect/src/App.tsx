import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ProspectShell } from '@/components/layout/ProspectShell'
import { ChatPage } from '@/pages/ChatPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2_000,
      refetchOnWindowFocus: false,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ProspectShell>
        <ChatPage />
      </ProspectShell>
    </QueryClientProvider>
  )
}
