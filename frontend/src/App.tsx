import { BrowserRouter, Routes, Route } from 'react-router-dom';
import MainLayout from './components/Layout/MainLayout';
import MemoryPage from './components/Memory/MemoryPage';
import SettingsPage from './components/Settings/SettingsPage';
import { useUsers } from './hooks/useUsers';
import type { User } from './types';

export interface AppContextValue {
  selectedUser: User | null;
  setSelectedUser: (user: User | null) => void;
}

function App() {
  const { users, selectedUser, setSelectedUser, loading: usersLoading } = useUsers();

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={
            <MainLayout
              users={users}
              selectedUser={selectedUser}
              setSelectedUser={setSelectedUser}
              usersLoading={usersLoading}
            />
          }
        />
        <Route
          path="/memory"
          element={<MemoryPage selectedUser={selectedUser} />}
        />
        <Route
          path="/settings"
          element={<SettingsPage selectedUser={selectedUser} />}
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
