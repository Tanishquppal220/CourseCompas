import Layout from "#components/layout";
import { ChatWindow } from "#components/chat-window";
function App() {
  return (
    <div className="App grid min-h-screen grid-rows-[auto_1fr]">
      <Layout>
        <ChatWindow />
      </Layout>
    </div>
  );
}

export default App;
