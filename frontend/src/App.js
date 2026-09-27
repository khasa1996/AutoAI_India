import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import ChatDrawer from "./components/ChatDrawerFixed";
import Home from "./pages/Home";
import Compare from "./pages/Compare";
import Recommend from "./pages/Recommend";
import Cars from "./pages/Cars";
import EMI from "./pages/EMI";
import News from "./pages/News";
import BookCar from "./pages/BookCar";
import Showroom from "./pages/Showroom";
import ConfiguratorExperience from "./pages/ConfiguratorExperience";
import ConfiguratorHistory from "./pages/ConfiguratorHistory";
import ConfiguratorConversion from "./pages/ConfiguratorConversion";
import ConfiguratorAssetManager from "./pages/ConfiguratorAssetManager";
import ConfiguratorAssetUpload from "./pages/ConfiguratorAssetUpload";
import DemoConfigurator from "./pages/DemoConfigurator";
import Premium from "./pages/Premium";
import Dealer from "./pages/Dealer";
import DealerApply from "./pages/DealerApply";
import Admin from "./pages/Admin";
import About from "./pages/About";
import Login from "./pages/Login";
import MyBookings from "./pages/MyBookings";
import InstallPWA from "./components/InstallPWA";
import { Toaster } from "./components/ui/sonner";
import { I18nProvider } from "./lib/i18n";
import AppErrorBoundary from "./components/AppErrorBoundary";

function App() {
  const demoOnly =
    typeof window !== "undefined" && window.location.pathname === "/configurator-demo";

  return (
    <AppErrorBoundary>
      <I18nProvider>
        <BrowserRouter>
          {demoOnly ? (
            <Routes>
              <Route path="/configurator-demo" element={<DemoConfigurator />} />
            </Routes>
          ) : (
            <div className="App bg-[#050505] text-white">
              <Navbar />
              <main>
                <Routes>
                  <Route path="/" element={<Home />} />
                  <Route path="/compare" element={<Compare />} />
                  <Route path="/recommend" element={<Recommend />} />
                  <Route path="/cars" element={<Cars />} />
                  <Route path="/emi" element={<EMI />} />
                  <Route path="/news" element={<News />} />
                  <Route path="/book/:carId" element={<BookCar />} />
                  <Route path="/showroom/:carId" element={<Showroom />} />
                  <Route path="/configurator/:variantId" element={<ConfiguratorExperience />} />
                  <Route path="/configurator/history" element={<ConfiguratorHistory />} />
                  <Route path="/configurator/conversion" element={<ConfiguratorConversion />} />
                  <Route path="/admin/configurator-assets" element={<ConfiguratorAssetManager />} />
                  <Route path="/admin/configurator-assets/upload" element={<ConfiguratorAssetUpload />} />
                  <Route path="/premium" element={<Premium />} />
                  <Route path="/dealer" element={<Dealer />} />
                  <Route path="/dealers/apply" element={<DealerApply />} />
                  <Route path="/admin" element={<Admin />} />
                  <Route path="/about" element={<About />} />
                  <Route path="/login" element={<Login />} />
                  <Route path="/my-bookings" element={<MyBookings />} />
                </Routes>
              </main>
              <Footer />
              <ChatDrawer />
              <InstallPWA />
              <Toaster />
            </div>
          )}
        </BrowserRouter>
      </I18nProvider>
    </AppErrorBoundary>
  );
}

export default App;
