import { useEffect } from "react";
import { Switch, Route, useLocation } from "wouter";
import { queryClient } from "./lib/queryClient";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/not-found";
import Dashboard from "@/pages/dashboard";
import ReportPage from "@/pages/report";
import HistoryPage from "@/pages/history";
import LoginPage from "@/pages/login";
import ActivityPage from "@/pages/activity";
import { AuthProvider, useAuth } from "@/hooks/use-auth";

function RequireAuth({ children }: { children: JSX.Element }) {
  const { loading, session } = useAuth();
  const [, setLocation] = useLocation();

  useEffect(() => {
    if (!loading && !session.authenticated) {
      setLocation("/login");
    }
  }, [loading, session.authenticated, setLocation]);

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center text-sm text-muted-foreground">
        Verifying operator session...
      </div>
    );
  }

  if (!session.authenticated) {
    return <div className="min-h-screen bg-background" />;
  }

  return children;
}

function LoginRoute() {
  const { loading, session } = useAuth();
  const [, setLocation] = useLocation();

  useEffect(() => {
    if (!loading && session.authenticated) {
      setLocation("/");
    }
  }, [loading, session.authenticated, setLocation]);

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center text-sm text-muted-foreground">
        Verifying operator session...
      </div>
    );
  }

  if (session.authenticated) {
    return <div className="min-h-screen bg-background" />;
  }

  return <LoginPage />;
}

function Router() {
  return (
    <Switch>
      <Route path="/login" component={LoginRoute} />
      <Route path="/">
        <RequireAuth>
          <Dashboard />
        </RequireAuth>
      </Route>
      <Route path="/report">
        <RequireAuth>
          <ReportPage />
        </RequireAuth>
      </Route>
      <Route path="/report/:id">
        {(params) => (
          <RequireAuth>
            <ReportPage params={params} />
          </RequireAuth>
        )}
      </Route>
      <Route path="/history">
        <RequireAuth>
          <HistoryPage />
        </RequireAuth>
      </Route>
      <Route path="/activity">
        <RequireAuth>
          <ActivityPage />
        </RequireAuth>
      </Route>
      <Route component={NotFound} />
    </Switch>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <TooltipProvider>
          <Toaster />
          <Router />
        </TooltipProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
