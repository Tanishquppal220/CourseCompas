import { useState, useEffect } from "react";

const Navbar = () => {
    const [backendStatus, setBackendStatus] = useState<boolean | null>(null);

    useEffect(() => {
        const checkBackendStatus = async () => {
            try {
                const response = await fetch("http://localhost:8000/api/status");
                if (response.ok) {
                    setBackendStatus(true);
                } else {
                    setBackendStatus(false);
                }
            } catch (error) {
                setBackendStatus(false);
                console.error("Error checking backend status:", error);
            }
        }
        checkBackendStatus();
    }, []);

    return (
      <nav className=" p-4">
        <div className="container mx-auto flex items-center justify-between">
          <div className=" font-bold text-xl">CourseCompass</div>
          <div className="space-x-4">
            <a href="/" className="">
              Home
            </a>
            <a href="/about" className="">
              About
            </a>
            <a href="/contact" className="">
              Contact
            </a>
            <div className="container mx-auto mt-2">
              <span className="text-gray-300">Backend Status: </span>
              {backendStatus === true ? (
                <span className="text-green-500">Online</span>
              ) : backendStatus === false ? (
                <span className="text-red-500">Offline</span>
              ) : (
                <span className="text-yellow-500">Checking...</span>
              )}
            </div>
          </div>
        </div>
        {/* Badge to Check the Backend Status by calling backend*/}
      </nav>
    );
}

export default Navbar