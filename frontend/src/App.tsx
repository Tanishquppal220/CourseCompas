import Layout from "#components/layout";
import { ChatWindow } from "#components/chat-window";
import { Routes, Route } from "react-router-dom";
import { Login } from "./pages/Login";
import { Register } from "./pages/Register";
import { Profile } from "./pages/Profile";

function App() {
  return (
    <div className="App grid min-h-screen grid-rows-[auto_1fr]">
      <Layout>
        <Routes>
          <Route path="/" element={<ChatWindow />} />
          <Route path="/chat/:id" element={<ChatWindow />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/profile" element={<Profile />} />
        </Routes>
      </Layout>
    </div>
  );
}

export default App;
